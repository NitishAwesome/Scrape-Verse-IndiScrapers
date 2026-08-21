"""Abstract scraper client interface."""

from abc import ABC, abstractmethod

from backend.scraper.models import RawScrapePayload


class ScraperClient(ABC):
    """Contract implemented by mock and Bright Data clients."""

    @abstractmethod
    def execute(
        self,
        *,
        target_url: str | None = None,
        trigger_failure: bool = False,
    ) -> RawScrapePayload:
        """Run a scrape and return raw records before normalization."""
