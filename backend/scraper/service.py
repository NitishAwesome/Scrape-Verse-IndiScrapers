"""Public scraping service — primary interface for Person 2 (automation)."""

import logging

from backend.scraper.base import ScraperClient
from backend.scraper.brightdata_client import BrightDataClient
from backend.scraper.config import ScraperMode, ScraperSettings, get_settings
from backend.scraper.exceptions import ScraperError, ScraperExecutionError, ScraperValidationError
from backend.scraper.mock_client import MockScraperClient
from backend.scraper.models import ScrapeResult, ScrapeStatus
from backend.scraper.normalizer import normalize_records
from backend.scraper.validator import validate_records

logger = logging.getLogger(__name__)


def create_scraper_client(settings: ScraperSettings | None = None) -> ScraperClient:
    """Factory: returns mock or Bright Data client based on SCRAPER_MODE."""
    resolved = settings or get_settings()

    if resolved.scraper_mode == ScraperMode.BRIGHTDATA:
        logger.debug("Using BrightDataClient")
        return BrightDataClient(resolved)

    logger.debug("Using MockScraperClient")
    return MockScraperClient(resolved)


class ScraperService:
    """
    Orchestrates scraper execution, normalization, and validation.

    Person 2 should import and call this class — not Bright Data internals.
    """

    def __init__(
        self,
        client: ScraperClient | None = None,
        settings: ScraperSettings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or create_scraper_client(self.settings)

    def execute(
        self,
        *,
        target_url: str | None = None,
        trigger_failure: bool = False,
    ) -> ScrapeResult:
        """
        Run the full scraping pipeline.

        Returns a ScrapeResult with status 'success' or 'failed'.
        """
        collector_id = self._collector_id()

        try:
            raw_payload = self.client.execute(
                target_url=target_url,
                trigger_failure=trigger_failure,
            )
        except ScraperExecutionError as exc:
            logger.error("Scraper execution failed: %s", exc)
            return ScrapeResult(
                collector_id=collector_id,
                status=ScrapeStatus.FAILED,
                records_extracted=0,
                data=[],
                error=str(exc),
            )
        except ScraperError as exc:
            logger.exception("Unexpected scraper error")
            return ScrapeResult(
                collector_id=collector_id,
                status=ScrapeStatus.FAILED,
                records_extracted=0,
                data=[],
                error=str(exc),
            )

        if raw_payload.error:
            logger.warning("Scraper returned execution error: %s", raw_payload.error)
            return ScrapeResult(
                collector_id=raw_payload.collector_id,
                status=ScrapeStatus.FAILED,
                records_extracted=0,
                data=[],
                error=raw_payload.error,
            )

        if not raw_payload.records:
            logger.warning("Scraper returned an empty record set")
            return ScrapeResult(
                collector_id=raw_payload.collector_id,
                status=ScrapeStatus.FAILED,
                records_extracted=0,
                data=[],
                error="Scrape returned no records",
            )

        try:
            normalized = normalize_records(raw_payload.records)
            validate_records(normalized)
        except ScraperValidationError as exc:
            logger.warning("Validation failed: %s", exc.field_errors)
            return ScrapeResult(
                collector_id=raw_payload.collector_id,
                status=ScrapeStatus.FAILED,
                records_extracted=0,
                data=[],
                error=f"Validation failed: {', '.join(exc.field_errors)}",
            )

        logger.info("Scrape succeeded with %d record(s)", len(normalized))
        return ScrapeResult(
            collector_id=raw_payload.collector_id,
            status=ScrapeStatus.SUCCESS,
            records_extracted=len(normalized),
            data=normalized,
        )

    def execute_dict(
        self,
        *,
        target_url: str | None = None,
        trigger_failure: bool = False,
    ) -> dict:
        """Convenience wrapper returning a JSON-serializable dictionary."""
        return self.execute(
            target_url=target_url,
            trigger_failure=trigger_failure,
        ).to_dict()

    def _collector_id(self) -> str:
        if self.settings.scraper_mode == ScraperMode.BRIGHTDATA:
            return self.settings.brightdata_collector_id or "unknown_collector"
        return self.settings.mock_collector_id


def run_scrape(
    *,
    target_url: str | None = None,
    trigger_failure: bool = False,
    fail: bool = False,
) -> dict:
    """Module-level helper returning dictionary result."""
    should_fail = trigger_failure or fail
    return ScraperService().execute_dict(
        target_url=target_url,
        trigger_failure=should_fail,
    )
