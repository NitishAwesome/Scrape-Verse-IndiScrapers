"""Local scraper client that reads mock-site/index.html."""

import logging
from html.parser import HTMLParser
from pathlib import Path

from backend.scraper.base import ScraperClient
from backend.scraper.config import ScraperSettings
from backend.scraper.exceptions import ScraperExecutionError
from backend.scraper.models import RawScrapePayload

logger = logging.getLogger(__name__)


class _MultiProductHTMLParser(HTMLParser):
    """Extract all product cards from the mock e-commerce page."""

    def __init__(self, selectors: dict[str, str] | None = None) -> None:
        super().__init__()
        self.records: list[dict[str, Any]] = []
        self._current_record: dict[str, Any] | None = None
        self._active_field: str | None = None
        self._buffer: list[str] = []
        self._card_depth: int = 0
        self._single_title: str | None = None
        self._single_price: str | None = None
        self._single_status: str | None = None
        self.selectors = selectors or {
            "title": ".product-title",
            "price": ".product-price",
            "stock_status": ".product-status",
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v or "" for k, v in attrs}
        classes = [c.strip() for c in attr_dict.get("class", "").split() if c.strip()]

        if "product-card" in classes:
            self._card_depth = 1
            self._current_record = {
                "title": "",
                "price": "",
                "stock_status": "",
                "rating": attr_dict.get("data-rating"),
                "category": attr_dict.get("data-category"),
                "product_url": None,
                "product_id": attr_dict.get("data-product-id"),
            }
            return
        elif self._card_depth > 0:
            self._card_depth += 1
            if tag == "a" and ("product-link" in classes or "product_link" in classes or attr_dict.get("href")):
                if self._current_record is not None and attr_dict.get("href"):
                    self._current_record["product_url"] = attr_dict.get("href")

        # Field matching inside card or single-product page
        matched_field = None
        for field, sel in self.selectors.items():
            if sel.startswith(".") and sel[1:] in classes:
                matched_field = field
                break

        if not matched_field:
            if "product-rating" in classes:
                matched_field = "rating"
            elif "product-category" in classes:
                matched_field = "category"
            elif "product-id-tag" in classes:
                matched_field = "product_id"

        if matched_field:
            self._active_field = matched_field
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._active_field:
            self._buffer.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if self._active_field:
            text = " ".join(p for p in self._buffer if p).strip()
            if self._current_record is not None:
                if self._active_field == "product_id" and text.startswith("ID:"):
                    self._current_record["product_id"] = text.replace("ID:", "").strip()
                else:
                    self._current_record[self._active_field] = text
            else:
                if self._active_field == "title":
                    self._single_title = text
                elif self._active_field == "price":
                    self._single_price = text
                elif self._active_field == "stock_status":
                    self._single_status = text
            self._active_field = None
            self._buffer = []

        if self._card_depth > 0:
            self._card_depth -= 1
            if self._card_depth == 0 and self._current_record is not None:
                if self._current_record.get("title") or self._current_record.get("price"):
                    self.records.append(self._current_record)
                self._current_record = None


class MockScraperClient(ScraperClient):
    """Development client that scrapes the local mock e-commerce page."""

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        selectors: dict[str, str] | None = None,
    ) -> None:
        self.settings = settings or ScraperSettings()
        self.selectors = selectors

    def execute(
        self,
        *,
        target_url: str | None = None,
        trigger_failure: bool = False,
    ) -> RawScrapePayload:
        logger.info(
            "Executing mock scraper (failure_mode=%s, target_url=%s)",
            trigger_failure,
            target_url or str(self.settings.mock_site_path),
        )

        if trigger_failure:
            return RawScrapePayload(
                collector_id=self.settings.mock_collector_id,
                records=[],
                error="SelectorNotFound: .product-title, .product-price, .product-status",
            )

        site_path = self._resolve_site_path()
        html = site_path.read_text(encoding="utf-8")
        parser = _MultiProductHTMLParser(selectors=self.selectors)
        parser.feed(html)

        # Use parsed multi-product records if found
        records = parser.records
        if not records and (parser._single_title or parser._single_price or parser._single_status):
            records = [
                {
                    "title": parser._single_title or "",
                    "price": parser._single_price or "",
                    "stock_status": parser._single_status or "",
                }
            ]

        if not records:
            raise ScraperExecutionError(
                f"Could not extract product data from mock site: {site_path}"
            )

        logger.info("Mock scraper extracted %d records from %s", len(records), site_path)
        return RawScrapePayload(
            collector_id=self.settings.mock_collector_id,
            records=records,
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
