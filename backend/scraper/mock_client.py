"""Local scraper client that reads mock-site/index.html."""

import logging
from html.parser import HTMLParser
from pathlib import Path

from backend.scraper.base import ScraperClient
from backend.scraper.config import ScraperSettings
from backend.scraper.exceptions import ScraperExecutionError
from backend.scraper.models import RawScrapePayload

logger = logging.getLogger(__name__)


class _ProductHTMLParser(HTMLParser):
    """Extract product fields from the mock e-commerce page."""

    def __init__(self) -> None:
        super().__init__()
        self._active_class: str | None = None
        self.title: str | None = None
        self.price: str | None = None
        self.stock_status: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "p" and tag != "h2":
            return

        class_map = dict(attrs)
        css_class = class_map.get("class")
        if css_class in {"product-title", "product-price", "product-status"}:
            self._active_class = css_class
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._active_class:
            self._buffer.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if not self._active_class:
            return

        value = " ".join(part for part in self._buffer if part).strip()
        if self._active_class == "product-title":
            self.title = value
        elif self._active_class == "product-price":
            self.price = value
        elif self._active_class == "product-status":
            self.stock_status = value

        self._active_class = None
        self._buffer = []


class MockScraperClient(ScraperClient):
    """Development client that scrapes the local mock e-commerce page."""

    def __init__(self, settings: ScraperSettings | None = None) -> None:
        self.settings = settings or ScraperSettings()

    def execute(self, *, trigger_failure: bool = False) -> RawScrapePayload:
        logger.info(
            "Executing mock scraper (collector=%s, trigger_failure=%s)",
            self.settings.mock_collector_id,
            trigger_failure,
        )

        if trigger_failure:
            return RawScrapePayload(
                collector_id=self.settings.mock_collector_id,
                records=[],
                error="SelectorNotFound: .product-price",
            )

        site_path = self._resolve_site_path()
        html = site_path.read_text(encoding="utf-8")
        parser = _ProductHTMLParser()
        parser.feed(html)

        if not parser.title and not parser.price and not parser.stock_status:
            raise ScraperExecutionError(
                f"Could not extract product data from mock site: {site_path}"
            )

        return RawScrapePayload(
            collector_id=self.settings.mock_collector_id,
            records=[
                {
                    "title": parser.title,
                    "price": parser.price,
                    "stock_status": parser.stock_status,
                }
            ],
        )

    def _resolve_site_path(self) -> Path:
        site_path = self.settings.mock_site_path
        if site_path.is_absolute():
            resolved = site_path
        else:
            resolved = Path.cwd() / site_path

        if not resolved.exists():
            raise ScraperExecutionError(f"Mock site not found: {resolved}")

        return resolved
