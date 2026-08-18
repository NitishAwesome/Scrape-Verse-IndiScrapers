import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure root path is accessible for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.scraper.brightdata_client import BrightDataClient
from backend.scraper.config import ScraperMode, ScraperSettings
from backend.scraper.exceptions import ScraperExecutionError, ScraperValidationError
from backend.scraper.mock_client import MockScraperClient
from backend.scraper.mock_scraper import run_scrape, run_scraper
from backend.scraper.models import ProductRecord, RawScrapePayload, ScrapeResult, ScrapeStatus
from backend.scraper.normalizer import (
    normalize_price,
    normalize_record,
    normalize_records,
    normalize_stock_status,
    normalize_title,
)
from backend.scraper.service import ScraperService
from backend.scraper.validator import validate_record, validate_records


class TestScraperEngine(unittest.TestCase):
    """Core tests for mock scraper engine execution."""

    def test_mock_scrape_success(self):
        result = run_scrape(fail=False)
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("records_extracted"), 1)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        product = result["data"][0]
        self.assertEqual(product.get("title"), "Wireless Gaming Mouse")
        self.assertEqual(product.get("price"), "$49.99")
        self.assertEqual(product.get("stock_status"), "In Stock")
        self.assertIsNone(result.get("error"))

    def test_mock_scrape_failure(self):
        result = run_scrape(fail=True)
        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(result.get("records_extracted"), 0)
        self.assertEqual(result.get("data"), [])
        self.assertIn("SelectorNotFound", result.get("error", ""))

    def test_legacy_run_scraper_alias(self):
        success_result = run_scraper(trigger_failure=False)
        self.assertEqual(success_result.get("status"), "success")

        fail_result = run_scraper(trigger_failure=True)
        self.assertEqual(fail_result.get("status"), "failed")


class TestNormalizer(unittest.TestCase):
    """Unit tests for data normalization layer."""

    def test_normalize_price(self):
        self.assertEqual(normalize_price("$49.99"), "$49.99")
        self.assertEqual(normalize_price("49.99"), "$49.99")
        self.assertEqual(normalize_price("1,299.50"), "$1299.50")
        self.assertEqual(normalize_price(None), "")
        self.assertEqual(normalize_price(""), "")

    def test_normalize_title(self):
        self.assertEqual(normalize_title("  Wireless   Gaming   Mouse  "), "Wireless Gaming Mouse")
        self.assertEqual(normalize_title(None), "")
        self.assertEqual(normalize_title(""), "")

    def test_normalize_stock_status(self):
        self.assertEqual(normalize_stock_status("in stock"), "In Stock")
        self.assertEqual(normalize_stock_status("AVAILABLE"), "In Stock")
        self.assertEqual(normalize_stock_status("instock"), "In Stock")
        self.assertEqual(normalize_stock_status("out of stock"), "Out of Stock")
        self.assertEqual(normalize_stock_status("sold out"), "Out of Stock")
        self.assertEqual(normalize_stock_status(None), "")

    def test_normalize_record(self):
        raw = {
            "title": "  Mechanical Keyboard  ",
            "price": "89.00",
            "status": "in stock",
        }
        product = normalize_record(raw)
        self.assertEqual(product.title, "Mechanical Keyboard")
        self.assertEqual(product.price, "$89.00")
        self.assertEqual(product.stock_status, "In Stock")


class TestValidator(unittest.TestCase):
    """Unit tests for record validation layer."""

    def test_validate_valid_record(self):
        valid = ProductRecord(title="Sample Item", price="$19.99", stock_status="In Stock")
        validate_record(valid)
        validate_records([valid])

    def test_validate_missing_title(self):
        invalid = ProductRecord(title="   ", price="$19.99", stock_status="In Stock")
        with self.assertRaises(ScraperValidationError):
            validate_record(invalid)

    def test_validate_missing_price(self):
        invalid = ProductRecord(title="Sample Item", price="", stock_status="In Stock")
        with self.assertRaises(ScraperValidationError):
            validate_record(invalid)

    def test_validate_missing_stock_status(self):
        invalid = ProductRecord(title="Sample Item", price="$19.99", stock_status="")
        with self.assertRaises(ScraperValidationError):
            validate_record(invalid)

    def test_validate_empty_record_list(self):
        with self.assertRaises(ScraperValidationError):
            validate_records([])


class TestScraperServiceEdgeCases(unittest.TestCase):
    """Tests covering empty responses, invalid data, and API failures in ScraperService."""

    def test_empty_response(self):
        mock_client = MagicMock()
        mock_client.execute.return_value = RawScrapePayload(
            collector_id="c_test_empty",
            records=[],
            error=None,
        )
        service = ScraperService(client=mock_client)
        result = service.execute()
        self.assertEqual(result.status, ScrapeStatus.FAILED)
        self.assertIn("no records", result.error.lower())

    def test_invalid_response_data(self):
        mock_client = MagicMock()
        # Missing price and title in raw payload
        mock_client.execute.return_value = RawScrapePayload(
            collector_id="c_test_invalid",
            records=[{"title": "", "price": "", "status": ""}],
            error=None,
        )
        service = ScraperService(client=mock_client)
        result = service.execute()
        self.assertEqual(result.status, ScrapeStatus.FAILED)
        self.assertIn("Validation failed", result.error)

    def test_api_failure_exception(self):
        mock_client = MagicMock()
        mock_client.execute.side_effect = ScraperExecutionError("Connection refused")
        service = ScraperService(client=mock_client)
        result = service.execute()
        self.assertEqual(result.status, ScrapeStatus.FAILED)
        self.assertIn("Connection refused", result.error)

    def test_raw_payload_with_error(self):
        mock_client = MagicMock()
        mock_client.execute.return_value = RawScrapePayload(
            collector_id="c_test_err",
            records=[],
            error="Rate limit exceeded",
        )
        service = ScraperService(client=mock_client)
        result = service.execute()
        self.assertEqual(result.status, ScrapeStatus.FAILED)
        self.assertEqual(result.error, "Rate limit exceeded")


class TestBrightDataClient(unittest.TestCase):
    """Tests for BrightDataClient credential validation and response extraction."""

    def test_missing_credentials_raises(self):
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token=None,
            brightdata_collector_id=None,
        )
        with self.assertRaises(ScraperExecutionError):
            BrightDataClient(settings)

    def test_extract_records_formats(self):
        # List format
        self.assertEqual(
            BrightDataClient._extract_records([{"title": "Item 1"}]),
            [{"title": "Item 1"}],
        )
        # Dict with data key
        self.assertEqual(
            BrightDataClient._extract_records({"data": [{"title": "Item 2"}]}),
            [{"title": "Item 2"}],
        )
        # Dict with results key
        self.assertEqual(
            BrightDataClient._extract_records({"results": [{"title": "Item 3"}]}),
            [{"title": "Item 3"}],
        )


if __name__ == "__main__":
    unittest.main()