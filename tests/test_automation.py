import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure root path is accessible for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

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
from backend.main import app
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

    def test_extract_with_selectors(self):
        selectors = {
            "title": ".main-title",
            "price": "#special-price",
            "stock_status": ".inventory-status",
        }
        extracted = self.analyzer.extract_with_selectors(self.sample_html, selectors)
        self.assertEqual(extracted.get("title"), "Mechanical Gaming Keyboard")
        self.assertEqual(extracted.get("price"), "$129.99")
        self.assertEqual(extracted.get("stock_status"), "In Stock")


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

    def test_demo_mutation_scenario_product_price_to_current_price(self):
        """
        Demo Scenario:
        Initial selector: .product-price
        Mutated HTML: <div class="current-price">$49.99</div>
        Result: .product-price fails -> .current-price discovered -> healed with $49.99.
        """
        mutated_html = """
        <div class="product-card">
            <h2 class="product-title">Wireless Gaming Mouse</h2>
            <div class="current-price">$49.99</div>
            <p class="product-status">In Stock</p>
        </div>
        """
        manager = HealingManager()
        result: HealingResult = manager.heal_html(
            html_content=mutated_html,
            initial_selectors={
                "title": ".product-title",
                "price": ".product-price",
                "stock_status": ".product-status",
            },
        )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.repaired)
        self.assertGreater(len(result.attempts), 0)

        first_repair = result.selector_repairs[0]
        self.assertEqual(first_repair.old_selector, ".product-price")
        self.assertEqual(first_repair.new_selector, ".current-price")
        self.assertEqual(first_repair.field, "price")

        first_event = result.attempts[0]
        self.assertTrue(first_event.validation_result)
        self.assertEqual(first_event.status, "success")

    def test_batch_healing_simultaneous_multi_field_mutation(self):
        """Test batch healing repair of title, price, and stock in one cycle."""
        multi_html = """
        <div class="product-card">
            <h2 class="product-name">Pro Mechanical Keyboard</h2>
            <span class="current-price">$129.99</span>
            <span class="availability">In Stock</span>
        </div>
        """
        manager = HealingManager()
        result = manager.heal_html(
            html_content=multi_html,
            initial_selectors={
                "title": ".product-title",
                "price": ".product-price",
                "stock_status": ".product-status",
            },
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(result.repaired)
        self.assertEqual(len(result.attempts), 1)  # All 3 healed in batch 1 attempt!
        self.assertEqual(len(result.selector_repairs), 3)

        repaired_map = {r.field: r.new_selector for r in result.selector_repairs}
        self.assertEqual(repaired_map.get("title"), ".product-name")
        self.assertEqual(repaired_map.get("price"), ".current-price")
        self.assertEqual(repaired_map.get("stock_status"), ".availability")

    def test_dynamic_repair_two_fields(self):
        """Test dynamic repair when exactly two selectors are broken."""
        two_field_html = """
        <div class="product-card">
            <h2 class="product-title">Gaming Headset</h2>
            <div class="current-price">$79.99</div>
            <div class="availability">Only 2 Left</div>
        </div>
        """
        manager = HealingManager()
        result = manager.heal_html(
            html_content=two_field_html,
            initial_selectors={
                "title": ".product-title",
                "price": ".product-price",
                "stock_status": ".product-status",
            },
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(result.repaired)
        self.assertEqual(len(result.selector_repairs), 2)
        repaired_fields = {r.field for r in result.selector_repairs}
        self.assertEqual(repaired_fields, {"price", "stock_status"})

    def test_configurable_max_retries_limit(self):
        """Test that max_retries limit is strictly enforced."""
        always_fail_html = "<div><p>Empty content without target fields</p></div>"
        manager = HealingManager(max_retries=4)
        self.assertEqual(manager.max_retries, 4)
        result = manager.heal_html(
            html_content=always_fail_html,
            initial_selectors={"title": ".non-existent", "price": ".missing-price"},
        )
        self.assertFalse(result.repaired)
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.attempts), 4)
        self.assertIn("Exhausted maximum retry limit", result.error)



class TestHealingRouter(unittest.TestCase):
    """Tests for FastAPI endpoints mounted from healing_router."""

    def setUp(self):
        self.client = TestClient(app)

    def test_get_healing_status_endpoint(self):
        response = self.client.get("/api/healing/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "online")
        self.assertEqual(body.get("module"), "self-healing")
        self.assertIn("SelectorNotFound", body.get("supported_failure_types", []))

    def test_post_healing_demo_endpoint(self):
        response = self.client.post("/api/healing/demo")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "success")
        self.assertTrue(body.get("repaired"))
        self.assertEqual(body.get("old_selector"), ".product-price")
        self.assertEqual(body.get("new_selector"), ".current-price")
        self.assertTrue(body.get("validation_result"))
        self.assertIn("healing_event", body)
        self.assertIn("healing_result", body)

    def test_get_healing_demo_endpoint(self):
        response = self.client.get("/api/healing/demo")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "success")
        self.assertEqual(body.get("new_selector"), ".current-price")

    def test_post_healing_test_endpoint(self):
        response = self.client.post("/api/healing/test")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "success")
        self.assertTrue(body.get("repaired"))
        self.assertEqual(body.get("failure_type"), "ValidationError")
        self.assertEqual(body.get("old_selector"), ".product-price")
        self.assertEqual(body.get("new_selector"), ".current-price")
        self.assertGreaterEqual(body.get("confidence"), 0.5)
        self.assertEqual(body.get("retry_count"), 1)
        self.assertEqual(body.get("validation"), "passed")
        self.assertIn("message", body)
        self.assertIn("data", body)
        self.assertEqual(body["data"][0]["price"], "$49.99")


    def test_post_healing_multi_demo_endpoint(self):
        """Test multi-selector healing endpoint repairing title, price, and stock across full catalog."""
        response = self.client.post("/api/healing/multi-demo")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "success")
        self.assertTrue(body.get("repaired"))
        self.assertLessEqual(body.get("attempts", 0), 3)
        self.assertEqual(body.get("validation"), "passed")

        repaired_sel = body.get("repaired_selectors", {})
        self.assertEqual(repaired_sel.get("title"), ".product-name")
        self.assertEqual(repaired_sel.get("price"), ".current-price")
        self.assertEqual(repaired_sel.get("stock_status"), ".availability")

        final_data = body.get("final_data", [])
        self.assertGreaterEqual(len(final_data), 30)
        self.assertEqual(final_data[0]["title"], "ProGear Wireless RGB Gaming Mouse")
        self.assertEqual(final_data[0]["price"], "$49.99")
        self.assertEqual(final_data[0]["stock_status"], "In Stock")

        repairs = body.get("repairs", [])
        self.assertEqual(len(repairs), 3)
        for r in repairs:
            self.assertIn("field", r)
            self.assertIn("old_selector", r)
            self.assertIn("new_selector", r)
            self.assertGreaterEqual(r.get("confidence", 0), 0.5)

    def test_get_healing_multi_demo_endpoint(self):
        response = self.client.get("/api/healing/multi-demo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "success")
        self.assertGreaterEqual(len(response.json().get("final_data", [])), 30)

    def test_existing_endpoints_unaffected(self):
        root_resp = self.client.get("/")
        self.assertEqual(root_resp.status_code, 200)
        self.assertEqual(root_resp.json().get("status"), "online")

        with patch("backend.main.scraper_service.client") as mock_client:
            from backend.scraper.mock_client import MockScraperClient
            from backend.scraper.config import ScraperSettings, ScraperMode
            mock_client.execute.side_effect = MockScraperClient(
                ScraperSettings(scraper_mode=ScraperMode.MOCK)
            ).execute
            scrape_resp = self.client.get("/api/scrape")
            self.assertEqual(scrape_resp.status_code, 200)
            body = scrape_resp.json()
            self.assertEqual(body.get("status"), "success")
            self.assertGreaterEqual(len(body["data"]), 30)

    def test_post_healing_recover_endpoint_with_target_url(self):
        """Test that /api/healing/recover accepts target URL and executes unified 3-field repair."""
        response = self.client.post("/api/healing/recover?url=https://books.toscrape.com/catalogue/category/books/travel_2/index.html")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "success")
        self.assertTrue(body.get("repaired"))
        self.assertEqual(body.get("failures_detected"), 3)
        self.assertEqual(body.get("selectors_repaired"), 3)
        self.assertEqual(body.get("validation"), "passed")
        self.assertIn("repairs", body)
        self.assertEqual(len(body["repairs"]), 3)
        self.assertIn("final_data", body)


class TestDynamicLiveSelfHealing(unittest.TestCase):
    """Tests for dynamic unexpected DOM structure discovery, confidence scoring, and live healing."""

    def setUp(self):
        self.analyzer = DOMAnalyzer()
        self.repair_engine = SelectorRepairEngine(mock_mode=False, confidence_threshold=0.75)

    def test_dynamic_selector_discovery_unexpected_dom_structures(self):
        """Test discovering unexpected selectors like .item-cost, [data-testid='stock'], and h2.book-title."""
        unexpected_html = """
        <div class="store-catalog">
            <div class="product-item">
                <h2 class="book-title">The Secret Garden</h2>
                <div class="item-cost">£24.99</div>
                <span data-testid="stock" class="inventory-status">In Stock</span>
            </div>
        </div>
        """
        candidates = self.analyzer.analyze(unexpected_html)
        self.assertGreater(len(candidates), 0)

        # Check dynamic price candidate
        price_cand = self.analyzer.find_best_candidate(unexpected_html, target_field="price")
        self.assertIsNotNone(price_cand)
        self.assertEqual(price_cand.suggested_selector, ".item-cost")
        self.assertGreaterEqual(price_cand.confidence, 0.75)
        self.assertIn("numeric price", price_cand.reasoning.lower())

        # Check dynamic title candidate
        title_cand = self.analyzer.find_best_candidate(unexpected_html, target_field="title")
        self.assertIsNotNone(title_cand)
        self.assertIn("title", title_cand.suggested_selector)
        self.assertGreaterEqual(title_cand.confidence, 0.75)

        # Check dynamic stock candidate with data-testid
        stock_cand = self.analyzer.find_best_candidate(unexpected_html, target_field="stock_status")
        self.assertIsNotNone(stock_cand)
        self.assertEqual(stock_cand.suggested_selector, "[data-testid='stock']")
        self.assertGreaterEqual(stock_cand.confidence, 0.75)

    def test_confidence_threshold_filtering(self):
        """Test that low confidence candidates below 0.75 threshold are rejected in live mode."""
        low_confidence_html = "<div><p>Just some plain text without any price or stock keywords</p></div>"
        candidates = self.analyzer.analyze(low_confidence_html)
        repair = self.repair_engine.propose_repair(
            field="price",
            old_selector=".product-price",
            candidates=candidates,
        )
        self.assertEqual(repair.confidence, 0.0)
        self.assertIn("exceeding confidence threshold", repair.reasoning)

    def test_multi_candidate_fallback_sequence(self):
        """Test proposing ranked candidates for multi-candidate fallback sequence."""
        multi_cand_html = """
        <div class="card">
            <span class="bad-price">Free</span>
            <div class="real-price">$49.99</div>
        </div>
        """
        candidates = self.analyzer.analyze(multi_cand_html)
        ranked_repairs = self.repair_engine.propose_candidates_ranked(
            field="price",
            old_selector=".product-price",
            candidates=candidates,
        )
        self.assertGreater(len(ranked_repairs), 0)
        top_repair = ranked_repairs[0]
        self.assertEqual(top_repair.new_selector, ".real-price")
        self.assertGreaterEqual(top_repair.confidence, 0.75)

    def test_healing_manager_heal_live_with_mocked_dom_fetcher(self):
        """Test heal_live workflow with live DOM acquisition and dynamic selector repair."""
        live_html_fixture = """
        <!DOCTYPE html>
        <html>
        <body>
            <article class="product_pod">
                <h3><a title="A Light in the Attic" href="catalogue/a-light-in-the-attic_1000/index.html">A Light in the Attic</a></h3>
                <div class="product_price">
                    <p class="price_color">£51.77</p>
                    <p class="instock availability">In stock</p>
                </div>
            </article>
        </body>
        </html>
        """
        mock_dom_fetcher = MagicMock()
        mock_dom_fetcher.fetch.return_value = live_html_fixture

        manager = HealingManager(dom_fetcher=mock_dom_fetcher)
        result = manager.heal_live(
            target_url="https://books.toscrape.com/catalogue/category/books_1/index.html",
            initial_selectors={
                "title": ".broken-title",
                "price": ".broken-price",
                "stock_status": ".broken-status",
            },
        )
        self.assertTrue(result.repaired)
        self.assertEqual(result.status, "success")
        self.assertGreaterEqual(len(result.data), 1)
        first_record = result.data[0]
        self.assertEqual(first_record.get("title"), "A Light in the Attic")
        self.assertEqual(first_record.get("price"), "$51.77")
        self.assertEqual(first_record.get("stock_status"), "In Stock")


if __name__ == "__main__":
    unittest.main()

