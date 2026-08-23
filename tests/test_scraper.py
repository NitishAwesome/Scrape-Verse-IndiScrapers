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

    def setUp(self):
        from backend.scraper.state import runtime_state
        runtime_state.reset()
        self.mock_service = ScraperService(
            settings=ScraperSettings(scraper_mode=ScraperMode.MOCK)
        )

    def tearDown(self):
        from backend.scraper.state import runtime_state
        runtime_state.reset()

    def test_mock_scrape_success(self):
        result = self.mock_service.execute_dict(trigger_failure=False)
        self.assertEqual(result.get("status"), "success")
        self.assertGreaterEqual(result.get("records_extracted", 0), 30)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertGreaterEqual(len(result["data"]), 30)

        first_product = result["data"][0]
        self.assertEqual(first_product.get("title"), "ProGear Wireless RGB Gaming Mouse")
        self.assertEqual(first_product.get("price"), "$49.99")
        self.assertEqual(first_product.get("stock_status"), "In Stock")
        self.assertIsNone(result.get("error"))

    def test_mock_scrape_failure(self):
        result = self.mock_service.execute_dict(trigger_failure=True)
        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(result.get("records_extracted"), 0)
        self.assertEqual(result.get("data"), [])
        self.assertIn("SelectorNotFound", result.get("error", ""))

    def test_legacy_run_scraper_alias(self):
        success_result = self.mock_service.execute_dict(trigger_failure=False)
        self.assertEqual(success_result.get("status"), "success")
        self.assertGreaterEqual(success_result.get("records_extracted", 0), 30)

        fail_result = self.mock_service.execute_dict(trigger_failure=True)
        self.assertEqual(fail_result.get("status"), "failed")

    def test_multi_product_catalog_attributes(self):
        """Verify all 40+ products have normalized canonical attributes."""
        result = self.mock_service.execute_dict(trigger_failure=False)
        products = result["data"]
        self.assertEqual(len(products), 42)
        for idx, prod in enumerate(products):
            self.assertTrue(prod["title"], f"Product {idx} missing title")
            self.assertTrue(prod["price"].startswith("$"), f"Product {idx} invalid price format")
            self.assertEqual(prod["stock_status"], "In Stock")


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
            "rating": "★ 4.9",
            "category": "keyboards",
            "product_url": "https://example.com/p1",
            "product_id": "PROD-102",
        }
        product = normalize_record(raw)
        self.assertEqual(product.title, "Mechanical Keyboard")
        self.assertEqual(product.price, "$89.00")
        self.assertEqual(product.stock_status, "In Stock")
        self.assertEqual(product.rating, 4.9)
        self.assertEqual(product.category, "Keyboards")
        self.assertEqual(product.product_url, "https://example.com/p1")
        self.assertEqual(product.product_id, "PROD-102")


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
    """Tests for BrightDataClient credential validation, response extraction, and async polling."""

    def test_missing_credentials_raises(self):
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token=None,
            brightdata_collector_id=None,
        )
        with self.assertRaises(ScraperExecutionError):
            BrightDataClient(settings)

    def test_token_sanitization_in_errors(self):
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token="super_secret_token_12345",
            brightdata_collector_id="c_test",
        )
        client = BrightDataClient(settings)
        sanitized = client._sanitize_error("Error connecting with Bearer super_secret_token_12345 to API")
        self.assertNotIn("super_secret_token_12345", sanitized)
        self.assertIn("[REDACTED_API_TOKEN]", sanitized)

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

    @patch("time.sleep", return_value=None)
    def test_brightdata_immediate_trigger_and_polling_flow(self, mock_sleep):
        """Test real-time immediate trigger (/dca/trigger_immediate) and response_id polling."""
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token="test_token",
            brightdata_collector_id="c_mt3d61eq4viqmv3f4",
            brightdata_timeout_seconds=5.0,
        )
        client = BrightDataClient(settings)

        mock_http = MagicMock()
        # Immediate trigger returns 202 with response_id
        trigger_resp = MagicMock()
        trigger_resp.status_code = 202
        trigger_resp.json.return_value = {"response_id": "resp_999xyz"}

        # First poll returns 202 with Retry-After, second poll returns 200 data
        pending_resp = MagicMock()
        pending_resp.status_code = 202
        pending_resp.headers = {"retry-after": "2"}

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.headers = {}
        success_resp.json.return_value = [{"title": "Realtime Book", "price": "$14.99", "status": "In Stock"}]

        mock_http.post.return_value = trigger_resp
        mock_http.get.side_effect = [pending_resp, success_resp]

        identifier, is_immediate = client._trigger_collection(mock_http, "c_mt3d61eq4viqmv3f4", "https://books.toscrape.com/test")
        self.assertEqual(identifier, "resp_999xyz")
        self.assertTrue(is_immediate)

        records = client._fetch_results(mock_http, "c_mt3d61eq4viqmv3f4", identifier, is_immediate)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Realtime Book")

    def test_brightdata_result_level_error_detection(self):
        """Verify result-level errors (e.g. too_many_pages, rate_limit) raise immediately."""
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token="test_secret_token",
            brightdata_collector_id="c_mt3d61eq4viqmv3f4",
        )
        client = BrightDataClient(settings)

        error_payload = [
            {
                "input": {"url": "https://books.toscrape.com"},
                "error": "Request generated 70 pages and exceeded realtime job limit of 51 pages",
                "error_code": "too_many_pages",
            }
        ]

        with self.assertRaises(ScraperExecutionError) as ctx:
            client._check_result_errors(error_payload)

        self.assertIn("too_many_pages", str(ctx.exception))
        self.assertIn("exceeded realtime job limit", str(ctx.exception))
        self.assertNotIn("test_secret_token", str(ctx.exception))

    @patch("time.sleep", return_value=None)
    def test_brightdata_batch_fallback_polling(self, mock_sleep):
        """Test fallback to batch queue (/dca/trigger) when immediate trigger is rejected."""
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token="test_token",
            brightdata_collector_id="c_mt3d61eq4viqmv3f4",
            brightdata_timeout_seconds=5.0,
        )
        client = BrightDataClient(settings)

        mock_http = MagicMock()
        # Immediate trigger returns 404 (not supported), batch trigger returns 200 with collection_id
        imm_fail_resp = MagicMock()
        imm_fail_resp.status_code = 404
        imm_fail_resp.text = "Endpoint not found"

        batch_ok_resp = MagicMock()
        batch_ok_resp.status_code = 200
        batch_ok_resp.json.return_value = {"collection_id": "job_batch_123"}

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.headers = {}
        success_resp.json.return_value = [{"title": "Batch Item", "price": "$9.99", "status": "In Stock"}]

        mock_http.post.side_effect = [imm_fail_resp, batch_ok_resp]
        mock_http.get.return_value = success_resp

        identifier, is_immediate = client._trigger_collection(mock_http, "c_mt3d61eq4viqmv3f4", "https://example.com")
        self.assertEqual(identifier, "job_batch_123")
        self.assertFalse(is_immediate)

        records = client._fetch_results(mock_http, "c_mt3d61eq4viqmv3f4", identifier, is_immediate)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Batch Item")


class TestDataIntegrityAndFieldPreservation(unittest.TestCase):
    """Tests proving that optional fields (category, product_id) are never fabricated with fake defaults."""

    def test_null_category_and_product_id_remain_none(self):
        """Verify that missing category and product_id remain None without fake fallbacks."""
        raw_record = {
            "title": "Clean Code",
            "price": "$45.00",
            "stock_status": "In Stock",
        }
        normalized = normalize_record(raw_record)
        self.assertEqual(normalized.title, "Clean Code")
        self.assertEqual(normalized.price, "$45.00")
        self.assertEqual(normalized.stock_status, "In Stock")
        self.assertIsNone(normalized.category, "Category must be None when absent, not 'General'")
        self.assertIsNone(normalized.product_id, "Product ID must be None when absent, not 'rec_1'")

    def test_real_category_and_product_id_are_preserved(self):
        """Verify that genuine category and product_id from upstream sources are preserved."""
        raw_record = {
            "title": "A Light in the Attic",
            "price": "$51.77",
            "stock_status": "In Stock",
            "category": "Poetry",
            "product_id": "book_a_light_in_the_attic_1000",
            "rating": 3.0,
            "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        }
        normalized = normalize_record(raw_record)
        self.assertEqual(normalized.category, "Poetry")
        self.assertEqual(normalized.product_id, "book_a_light_in_the_attic_1000")
        self.assertEqual(normalized.rating, 3.0)

    def test_quality_score_focuses_on_required_contract_fields(self):
        """Verify that quality score computes 100% when required fields pass, even if optional fields are None."""
        from backend.automation.healing_manager import calculate_data_quality

        records = [
            {"title": "Book A", "price": "$10.00", "stock_status": "In Stock", "category": None, "product_id": None},
            {"title": "Book B", "price": "$20.00", "stock_status": "In Stock", "category": None, "product_id": None},
        ]
        quality = calculate_data_quality(records)
        self.assertEqual(quality["title_completeness"], 100.0)
        self.assertEqual(quality["price_completeness"], 100.0)
        self.assertEqual(quality["stock_completeness"], 100.0)
        self.assertEqual(quality["valid_record_ratio"], 100.0)
        self.assertEqual(quality["overall_quality_score"], 100.0)


if __name__ == "__main__":
    unittest.main()