"""Bright Data scraper client (used once account verification completes)."""

import logging
from typing import Any

import httpx

from backend.scraper.base import ScraperClient
from backend.scraper.config import ScraperSettings
from backend.scraper.exceptions import ScraperExecutionError
from backend.scraper.models import RawScrapePayload

logger = logging.getLogger(__name__)


class BrightDataClient(ScraperClient):
    """
    Executes a Bright Data collector and retrieves structured results.

    Credentials are read from environment variables via ScraperSettings.
    """

    def __init__(self, settings: ScraperSettings | None = None) -> None:
        self.settings = settings or ScraperSettings()
        self._validate_credentials()

    def execute(self, *, trigger_failure: bool = False) -> RawScrapePayload:
        if trigger_failure:
            logger.warning("trigger_failure is ignored for Bright Data client")

        collector_id = self.settings.brightdata_collector_id
        assert collector_id is not None  # validated in __init__

        logger.info("Triggering Bright Data collector: %s", collector_id)

        try:
            with httpx.Client(timeout=self.settings.brightdata_timeout_seconds) as client:
                snapshot_id = self._trigger_collection(client, collector_id)
                raw_records = self._fetch_results(client, collector_id, snapshot_id)
        except httpx.HTTPError as exc:
            logger.exception("Bright Data HTTP request failed")
            raise ScraperExecutionError(f"Bright Data API request failed: {exc}") from exc

        return RawScrapePayload(
            collector_id=collector_id,
            records=raw_records,
        )

    def _validate_credentials(self) -> None:
        if not self.settings.brightdata_api_token:
            raise ScraperExecutionError(
                "BRIGHTDATA_API_TOKEN is required when SCRAPER_MODE=brightdata"
            )
        if not self.settings.brightdata_collector_id:
            raise ScraperExecutionError(
                "BRIGHTDATA_COLLECTOR_ID is required when SCRAPER_MODE=brightdata"
            )

    def _auth_headers(self) -> dict[str, str]:
        token = self.settings.brightdata_api_token
        assert token is not None
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _trigger_collection(self, client: httpx.Client, collector_id: str) -> str | None:
        """
        Trigger collector execution.

        Returns an optional snapshot/job id when provided by the API.
        """
        url = f"{self.settings.brightdata_api_base_url}/dca/trigger"
        payload = {"collector": collector_id}

        response = client.post(url, headers=self._auth_headers(), json=payload)
        if response.status_code >= 400:
            raise ScraperExecutionError(
                f"Bright Data trigger failed ({response.status_code}): {response.text}"
            )

        body = response.json()
        snapshot_id = body.get("snapshot_id") or body.get("job_id")
        logger.debug("Bright Data trigger response snapshot_id=%s", snapshot_id)
        return snapshot_id

    def _fetch_results(
        self,
        client: httpx.Client,
        collector_id: str,
        snapshot_id: str | None,
    ) -> list[dict[str, Any]]:
        """Retrieve collector results and map them to raw record dictionaries."""
        if snapshot_id:
            url = (
                f"{self.settings.brightdata_api_base_url}/dca/get_result"
                f"?collector={collector_id}&snapshot_id={snapshot_id}"
            )
        else:
            url = f"{self.settings.brightdata_api_base_url}/dca/get_result?collector={collector_id}"

        response = client.get(url, headers=self._auth_headers())
        if response.status_code >= 400:
            raise ScraperExecutionError(
                f"Bright Data result fetch failed ({response.status_code}): {response.text}"
            )

        body = response.json()
        records = self._extract_records(body)
        logger.info("Bright Data returned %d raw record(s)", len(records))
        return records

    @staticmethod
    def _extract_records(body: Any) -> list[dict[str, Any]]:
        """Support common Bright Data response envelopes."""
        if isinstance(body, list):
            return [record for record in body if isinstance(record, dict)]

        if isinstance(body, dict):
            for key in ("data", "results", "records"):
                value = body.get(key)
                if isinstance(value, list):
                    return [record for record in value if isinstance(record, dict)]

        raise ScraperExecutionError("Bright Data response did not contain record data")
