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
    Executes a Bright Data Scraper Studio collector and retrieves structured results.

    Uses real-time immediate execution (/dca/trigger_immediate) with polling (/dca/get_result?response_id=...)
    with automatic fallback to batch execution (/dca/trigger).
    Credentials and settings are read from environment variables via ScraperSettings.
    Tokens are strictly masked in all logging and error reporting.
    """

    def __init__(self, settings: ScraperSettings | None = None) -> None:
        self.settings = settings or ScraperSettings()
        self._validate_credentials()

    def execute(
        self,
        *,
        target_url: str | None = None,
        trigger_failure: bool = False,
    ) -> RawScrapePayload:
        if trigger_failure:
            logger.warning("trigger_failure flag received; real Bright Data execution will proceed normally")

        collector_id = self.settings.brightdata_collector_id
        assert collector_id is not None

        effective_url = target_url or self.settings.target_url or "https://example.com"
        logger.info(
            "Triggering Bright Data Scraper Studio collector=%s for target_url=%s",
            collector_id,
            effective_url,
        )

        try:
            with httpx.Client(timeout=self.settings.brightdata_timeout_seconds) as client:
                identifier, is_immediate = self._trigger_collection(client, collector_id, effective_url)
                raw_records = self._fetch_results(client, collector_id, identifier, is_immediate)
        except httpx.HTTPError as exc:
            logger.exception("Bright Data HTTP request failed")
            raise ScraperExecutionError(f"Bright Data API request failed: {self._sanitize_error(str(exc))}") from exc

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

    def _sanitize_error(self, message: str) -> str:
        """Strip raw API tokens from error strings before logging or raising."""
        if self.settings.brightdata_api_token and self.settings.brightdata_api_token in message:
            return message.replace(self.settings.brightdata_api_token, "[REDACTED_API_TOKEN]")
        return message

    def _trigger_collection(
        self,
        client: httpx.Client,
        collector_id: str,
        target_url: str,
    ) -> tuple[str, bool]:
        """
        Trigger Scraper Studio collector.
        Attempts real-time immediate trigger (/dca/trigger_immediate) first,
        falling back to batch queue (/dca/trigger) if immediate trigger is not supported.

        Returns (identifier, is_immediate_mode).
        """
        immediate_url = (
            f"{self.settings.brightdata_api_base_url}/dca/trigger_immediate"
            f"?collector={collector_id}"
        )
        immediate_payload = {"url": target_url}

        logger.debug("POST %s with payload={'url': '%s'}", immediate_url, target_url)
        imm_response = client.post(immediate_url, headers=self._auth_headers(), json=immediate_payload)

        # Immediate trigger returns 200 or 202 with response_id
        if imm_response.status_code in {200, 202}:
            try:
                body = imm_response.json()
            except Exception:
                body = {}

            response_id = body.get("response_id")
            if response_id:
                logger.info("Real-time scraper triggered successfully (response_id=%s)", response_id)
                return str(response_id), True

        # If immediate trigger returns non-fatal or unsupported, attempt batch fallback
        logger.debug("Immediate trigger returned status %d; attempting batch trigger fallback", imm_response.status_code)
        batch_url = (
            f"{self.settings.brightdata_api_base_url}/dca/trigger"
            f"?collector={collector_id}&queue_next=1"
        )
        batch_payload = [{"url": target_url}]

        batch_response = client.post(batch_url, headers=self._auth_headers(), json=batch_payload)
        if batch_response.status_code >= 400:
            err_msg = self._sanitize_error(batch_response.text or imm_response.text)
            raise ScraperExecutionError(
                f"Bright Data trigger failed ({batch_response.status_code}): {err_msg}"
            )

        body = batch_response.json()
        job_id = (
            body.get("collection_id")
            or body.get("snapshot_id")
            or body.get("job_id")
            or body.get("response_id")
        )
        if not job_id:
            raise ScraperExecutionError("Bright Data trigger did not return a valid job or response identifier")

        logger.info("Batch scraper triggered successfully (job_id=%s)", job_id)
        return str(job_id), False

    def _fetch_results(
        self,
        client: httpx.Client,
        collector_id: str,
        identifier: str,
        is_immediate: bool,
    ) -> list[dict[str, Any]]:
        """Retrieve collector results with polling, exponential backoff, and Retry-After support."""
        import time

        start_time = time.time()
        poll_interval = 1.5
        max_interval = 5.0

        if is_immediate:
            poll_url = f"{self.settings.brightdata_api_base_url}/dca/get_result?response_id={identifier}"
        else:
            poll_url = f"{self.settings.brightdata_api_base_url}/dca/dataset?id={identifier}"

        logger.debug("Polling Bright Data results at: %s", poll_url)

        while True:
            response = client.get(poll_url, headers=self._auth_headers())

            # Read retry-after header if provided by Bright Data
            retry_after_hdr = response.headers.get("retry-after")
            sleep_duration = poll_interval
            if retry_after_hdr and retry_after_hdr.isdigit():
                sleep_duration = min(float(retry_after_hdr), max_interval)

            # HTTP 202 indicates collection in progress
            if response.status_code == 202:
                if time.time() - start_time >= self.settings.brightdata_timeout_seconds:
                    raise ScraperExecutionError(
                        f"Bright Data collector timed out waiting for results ({self.settings.brightdata_timeout_seconds}s)"
                    )
                logger.debug("Collector job pending (HTTP 202), sleeping %.1fs...", sleep_duration)
                time.sleep(sleep_duration)
                poll_interval = min(poll_interval * 1.3, max_interval)
                continue

            if response.status_code >= 400:
                err_msg = self._sanitize_error(response.text)
                raise ScraperExecutionError(
                    f"Bright Data result fetch failed ({response.status_code}): {err_msg}"
                )

            body = response.json()

            # Check if JSON body indicates pending / collecting status
            if isinstance(body, dict) and body.get("status") in {"running", "building", "pending", "collecting"}:
                if time.time() - start_time >= self.settings.brightdata_timeout_seconds:
                    raise ScraperExecutionError(
                        f"Bright Data collector timed out ({self.settings.brightdata_timeout_seconds}s)"
                    )
                logger.debug("Collector status '%s', sleeping %.1fs...", body.get("status"), sleep_duration)
                time.sleep(sleep_duration)
                poll_interval = min(poll_interval * 1.3, max_interval)
                continue

            # Check for result-level crawler errors (e.g. too_many_pages, rate_limit)
            self._check_result_errors(body)

            records = self._extract_records(body)
            logger.info("Bright Data returned %d raw record(s)", len(records))
            return records

    def _check_result_errors(self, body: Any) -> None:
        """Inspect payload for early result-level errors returned by Bright Data crawlers."""
        items = body if isinstance(body, list) else ([body] if isinstance(body, dict) else [])
        for item in items:
            if isinstance(item, dict):
                error = item.get("error")
                error_code = item.get("error_code")
                if error or error_code:
                    msg = f"Bright Data extraction error [{error_code or 'UNKNOWN'}]: {error or 'Unknown error'}"
                    raise ScraperExecutionError(self._sanitize_error(msg))

    @staticmethod
    def _extract_records(body: Any) -> list[dict[str, Any]]:
        """Support common Bright Data response envelopes and flatten nested item arrays (books, products, etc.)."""
        raw_list: list[Any] = []

        if isinstance(body, list):
            for item in body:
                if isinstance(item, dict):
                    nested_found = False
                    for key in ("books", "products", "items", "listings", "results", "data"):
                        sub_list = item.get(key)
                        if isinstance(sub_list, list) and sub_list:
                            raw_list.extend(sub_list)
                            nested_found = True
                            break
                    if not nested_found:
                        raw_list.append(item)
                else:
                    raw_list.append(item)
        elif isinstance(body, dict):
            for key in ("books", "products", "items", "listings", "results", "data", "records"):
                value = body.get(key)
                if isinstance(value, list):
                    raw_list = value
                    break
            if not raw_list and ("title" in body or "name" in body):
                raw_list = [body]

        valid_records = [record for record in raw_list if isinstance(record, dict) and not record.get("error")]
        if valid_records:
            return valid_records

        raise ScraperExecutionError("Bright Data response did not contain valid record data")
