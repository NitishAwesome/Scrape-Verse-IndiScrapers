import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure root path is accessible for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.automation import (
    DOMAnalyzer,
    FailureDetector,
    FailureType,
    HealingEvent,
    HealingManager,
    HealingResult,
    HealingStatus,
    HealingValidator,
    ScrapeFailure,
    SelectorRepair,
    SelectorRepairEngine,
)
from backend.scraper.models import ProductRecord, ScrapeResult, ScrapeStatus


class TestFailureDetector(unittest.TestCase):
    """Tests for FailureDetector."""

    def setUp(self):
        self.detector = FailureDetector()

    def test_failure_detection_when_data_is_empty(self):
        """1. Failure detection when data is empty."""
        empty_result = ScrapeResult(
            collector_id="c_test_empty",
            status=ScrapeStatus.SUCCESS,
            records_extracted=0,
            data=[],
            error=None,
        )
        failure = self.detector.detect(empty_result)
        self.assertIsNotNone(failure)
        self.assertEqual(failure.failure_type, FailureType.EMPTY_RESPONSE.value)
        self.assertIn("0", failure.error)

    def test_failure_detection_when_required_field_is_missing(self):
        """2. Failure detection when a required field is missing."""
        invalid_record_result = {
            "collector_id": "c_test_missing_price",
            "status": "success",
            "records_extracted": 1,
            "data": [
                {
                    "title": "Ergonomic Keyboard",
                    "price": "",  # Missing required price
                    "stock_status": "In Stock",
                }
            ],
            "error": None,
        }
        failure = self.detector.detect(invalid_record_result)
        self.assertIsNotNone(failure)
        self.assertEqual(failure.failure_type, FailureType.VALIDATION_ERROR.value)
        self.assertEqual(failure.field, "price")

    def test_failure_detection_selector_not_found(self):
        failed_result = ScrapeResult(
            collector_id="c_mock_123456",
            status=ScrapeStatus.FAILED,
            records_extracted=0,
            data=[],
            error="SelectorNotFound: .product-price",
        )
        failure = self.detector.detect(failed_result)
        self.assertIsNotNone(failure)
        self.assertEqual(failure.failure_type, FailureType.SELECTOR_NOT_FOUND.value)
        self.assertEqual(failure.field, "price")
        self.assertEqual(failure.old_selector, ".product-price")

    def test_no_failure_when_result_is_healthy(self):
        healthy_result = ScrapeResult(
            collector_id="c_mock_123456",
            status=ScrapeStatus.SUCCESS,
            records_extracted=1,
            data=[ProductRecord(title="Laptop", price="$999.00", stock_status="In Stock")],
            error=None,
        )
        failure = self.detector.detect(healthy_result)
        self.assertIsNone(failure)


class TestDOMAnalyzer(unittest.TestCase):
    """Tests for DOMAnalyzer candidate extraction."""

    def setUp(self):
        self.analyzer = DOMAnalyzer()
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <body>
            <div class="product-wrapper">
                <h1 class="main-title">Mechanical Gaming Keyboard</h1>
                <span class="price-tag-updated" id="special-price">$129.99</span>
                <div class="inventory-status">In Stock</div>
            </div>
        </body>
        </html>
        """

    def test_dom_candidate_detection(self):
        """3. DOM candidate detection."""
        candidates = self.analyzer.analyze(self.sample_html)
        self.assertGreater(len(candidates), 0)

        # Check price candidate detection
        price_cand = self.analyzer.find_best_candidate(self.sample_html, target_field="price")
        self.assertIsNotNone(price_cand)
        self.assertEqual(price_cand.field_hint, "price")
        self.assertIn("$129.99", price_cand.text)
        self.assertEqual(price_cand.suggested_selector, "#special-price")

        # Check title candidate detection
        title_cand = self.analyzer.find_best_candidate(self.sample_html, target_field="title")
        self.assertIsNotNone(title_cand)
        self.assertEqual(title_cand.field_hint, "title")
        self.assertIn("Keyboard", title_cand.text)

        # Check stock candidate detection
        stock_cand = self.analyzer.find_best_candidate(self.sample_html, target_field="stock_status")
        self.assertIsNotNone(stock_cand)
        self.assertEqual(stock_cand.field_hint, "stock_status")
        self.assertEqual(stock_cand.text, "In Stock")


class TestSelectorRepair(unittest.TestCase):
    """Tests for SelectorRepairEngine."""

    def test_successful_selector_repair_from_dom_candidates(self):
        """4. Successful selector repair using DOM candidates."""
        analyzer = DOMAnalyzer()
        html = "<div class='store'><span class='new-price-badge'>$49.99</span></div>"
        candidates = analyzer.analyze(html, target_field="price")

        repair_engine = SelectorRepairEngine(mock_mode=True)
        repair = repair_engine.propose_repair(
            field="price",
            old_selector=".product-price",
            candidates=candidates,
        )
        self.assertEqual(repair.field, "price")
        self.assertEqual(repair.old_selector, ".product-price")
        self.assertEqual(repair.new_selector, ".new-price-badge")
        self.assertGreater(repair.confidence, 0.5)
        self.assertIsNotNone(repair.reasoning)

    def test_failed_selector_repair_when_no_candidates_and_mock_disabled(self):
        """5. Failed selector repair when no candidates exist and mock LLM mode is disabled."""
        repair_engine = SelectorRepairEngine(mock_mode=False)
        repair = repair_engine.propose_repair(
            field="price",
            old_selector=".broken-price",
            candidates=[],
        )
        self.assertEqual(repair.confidence, 0.0)
        self.assertIn("No viable replacement", repair.reasoning)


class TestHealingValidator(unittest.TestCase):
    """Tests for HealingValidator."""

    def setUp(self):
        self.validator = HealingValidator()

    def test_successful_validation(self):
        """6. Successful validation of recovered scrape."""
        valid_payload = {
            "status": "success",
            "records_extracted": 1,
            "data": [
                {
                    "title": "Wireless Mouse",
                    "price": "$49.99",
                    "stock_status": "In Stock",
                }
            ],
            "error": None,
        }
        is_valid, reason = self.validator.validate(valid_payload, target_field="price")
        self.assertTrue(is_valid)
        self.assertIn("successful", reason.lower())

    def test_failed_validation_on_empty_or_failed_status(self):
        failed_payload = {"status": "failed", "records_extracted": 0, "data": [], "error": "SelectorNotFound"}
        is_valid, reason = self.validator.validate(failed_payload)
        self.assertFalse(is_valid)
        self.assertIn("failed", reason.lower())


class TestHealingManager(unittest.TestCase):
    """Tests for HealingManager lifecycle."""

    def test_healing_manager_successful_recovery(self):
        """7. Healing manager successful recovery."""
        # Simulated runner: fails on first run (trigger_failure=True), succeeds on retry (trigger_failure=False)
        def mock_runner(trigger_failure: bool = False):
            if trigger_failure:
                return {
                    "collector_id": "c_mock_123456",
                    "status": "failed",
                    "records_extracted": 0,
                    "data": [],
                    "error": "SelectorNotFound: .product-price",
                }
            return {
                "collector_id": "c_mock_123456",
                "status": "success",
                "records_extracted": 1,
                "data": [
                    {
                        "title": "Wireless Gaming Mouse",
                        "price": "$49.99",
                        "stock_status": "In Stock",
                    }
                ],
                "error": None,
            }

        manager = HealingManager()
        failed_initial_result = mock_runner(trigger_failure=True)

        result: HealingResult = manager.heal(
            initial_result=failed_initial_result,
            scrape_fn=mock_runner,
        )

        self.assertEqual(result.status, HealingStatus.SUCCESS.value)
        self.assertTrue(result.repaired)
        self.assertGreater(len(result.attempts), 0)
        self.assertGreater(len(result.selector_repairs), 0)
        self.assertIsNone(result.error)

        first_event: HealingEvent = result.attempts[0]
        self.assertEqual(first_event.status, HealingStatus.SUCCESS.value)
        self.assertEqual(first_event.failure_type, FailureType.SELECTOR_NOT_FOUND.value)

    def test_healing_manager_maximum_retry_protection(self):
        """8. Healing manager maximum retry protection (bounded retries)."""
        # Simulated runner that continually fails
        always_failing_runner = MagicMock(
            return_value={
                "collector_id": "c_broken",
                "status": "failed",
                "records_extracted": 0,
                "data": [],
                "error": "SelectorNotFound: .unfixable-element",
            }
        )

        manager = HealingManager(max_retries=2)
        initial_failed_result = always_failing_runner()

        result: HealingResult = manager.heal(
            initial_result=initial_failed_result,
            scrape_fn=always_failing_runner,
        )

        self.assertEqual(result.status, HealingStatus.FAILED.value)
        self.assertFalse(result.repaired)
        self.assertEqual(len(result.attempts), 2)
        self.assertIn("Exhausted maximum retry limit", result.error)


if __name__ == "__main__":
    unittest.main()
