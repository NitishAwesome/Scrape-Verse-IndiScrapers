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
        from backend.scraper.state import runtime_state
        runtime_state.reset()
        self.client = TestClient(app)

    def tearDown(self):
        from backend.scraper.state import runtime_state
        runtime_state.reset()

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

    def test_adaptive_healing_unseen_dom_structure(self):
        """
        Prove that self-healing discovers replacement selectors from an unseen DOM
        with zero occurrences of the demo selector names (.product-name, .current-price, .availability).
        """
        from backend.scraper.validator import validate_records

        unseen_html = """
        <div class="storefront-item-box">
            <h2 class="catalog-heading-x7">Quantum ANC Headphones</h2>
            <div class="weird-money-amount">$249.99</div>
            <span class="inventory-status-pill" data-testid="stock">In Stock (14 Units)</span>
        </div>
        """
        # 1. Assert that none of the 6 demo keywords exist in the test DOM
        forbidden_keywords = [
            "product-title", "product-name", "product-price",
            "current-price", "product-status", "availability"
        ]
        for kw in forbidden_keywords:
            self.assertNotIn(kw, unseen_html)

        manager = HealingManager()
        # 2. Start with completely broken/unrelated initial selectors
        initial_selectors = {
            "title": ".missing-heading-alpha",
            "price": ".nonexistent-price-tag",
            "stock_status": ".absent-stock-indicator",
        }

        # 3. Execute real healing pipeline
        result = manager.heal_html(
            html_content=unseen_html,
            initial_selectors=initial_selectors,
            scraper_id="unseen-custom-store",
        )

        # 4. Verify healing succeeded
        self.assertTrue(result.repaired)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.selector_repairs), 3)

        # 5. Verify replacement selectors were discovered dynamically (NOT the demo selectors)
        repaired_selectors = {r.field: r.new_selector for r in result.selector_repairs}
        for kw in [".product-name", ".current-price", ".availability"]:
            self.assertNotIn(kw, repaired_selectors.values())

        # 6. Verify extracted records and values
        self.assertGreaterEqual(len(result.data), 1)
        record = result.data[0]
        self.assertEqual(record.get("title"), "Quantum ANC Headphones")
        self.assertEqual(record.get("price"), "$249.99")
        self.assertEqual(record.get("stock_status"), "In Stock")

        # 7. Verify Pydantic schema validation succeeds on recovered record without error
        product_records = [ProductRecord(**d) for d in result.data]
        self.assertEqual(len(product_records), 1)
        validate_records(product_records)  # Validates required field contracts without raising ScraperValidationError
class TestPhase2SelfHealingReliability(unittest.TestCase):
    """
    Phase 2 test suite: Verifies reliability, metrics, candidate ranking,
    confidence safety gating, partial failure precision, and safe failure.
    """

    def setUp(self):
        self.manager = HealingManager()

    def test_partial_failure_single_field_repair(self):
        """
        Prove that when only ONE field fails (e.g. price class changed),
        the system repairs ONLY the broken field and preserves working selectors.
        """
        html = """
        <div class="product-item">
            <h2 class="title-alpha">Ergonomic Office Chair</h2>
            <div class="cost-value-x9">$199.99</div>
            <span class="stock-status-tag">In Stock</span>
        </div>
        """
        # initial selectors: title and stock_status are correct, price is broken
        initial_selectors = {
            "title": ".title-alpha",
            "price": ".old-broken-price-tag",
            "stock_status": ".stock-status-tag",
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="partial-test-1",
        )

        self.assertTrue(result.repaired)
        self.assertTrue(result.verified)
        self.assertEqual(result.status, "success")
        self.assertIn("price", result.fields_repaired)
        self.assertIn("price", result.fields_detected_as_broken)
        # title and stock_status should NOT be marked as broken
        self.assertNotIn("title", result.fields_detected_as_broken)
        self.assertNotIn("stock_status", result.fields_detected_as_broken)

        # Repaired dataset verification
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["title"], "Ergonomic Office Chair")
        self.assertEqual(result.data[0]["price"], "$199.99")
        self.assertEqual(result.data[0]["stock_status"], "In Stock")

    def test_partial_failure_dual_field_repair(self):
        """
        Prove that when TWO fields fail (title & price),
        only those two are repaired while stock_status is untouched.
        """
        html = """
        <div class="product-item">
            <h3 class="headline-text">Ultra-Wide 4K Monitor</h3>
            <span class="price_tag_color">$499.00</span>
            <span class="stock-valid-ind">In Stock</span>
        </div>
        """
        initial_selectors = {
            "title": ".obsolete-title-sel",
            "price": ".obsolete-price-sel",
            "stock_status": ".stock-valid-ind",  # working selector
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="partial-test-2",
        )

        self.assertTrue(result.repaired)
        self.assertEqual(set(result.fields_detected_as_broken), {"title", "price"})
        self.assertNotIn("stock_status", result.fields_detected_as_broken)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["title"], "Ultra-Wide 4K Monitor")
        self.assertEqual(result.data[0]["price"], "$499.00")

    def test_safe_failure_insufficient_evidence(self):
        """
        Prove that when the DOM contains insufficient evidence / low-confidence markup,
        the safety gate triggers, scraper is NOT patched, and FAILED status is returned safely.
        """
        # HTML with ambiguous text and no currency or inventory semantics
        unclear_html = """
        <div class="generic-container">
            <p class="random-blob">Some arbitrary unstructured content without price or stock</p>
        </div>
        """
        initial_selectors = {
            "title": ".broken-title",
            "price": ".broken-price",
            "stock_status": ".broken-status",
        }

        result = self.manager.heal_html(
            html_content=unclear_html,
            initial_selectors=initial_selectors,
            scraper_id="safe-failure-test",
        )

        # Must fail safely without inventing fake selectors or claiming success
        self.assertFalse(result.repaired)
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.data), 0)
        self.assertIsNotNone(result.error)

    def test_data_quality_and_recovery_metrics(self):
        """
        Prove that recovery metrics and data quality completeness percentages are computed accurately.
        """
        html = """
        <div class="product-item">
            <h1 class="main-prod-title">Smart Fitness Tracker</h1>
            <div class="main-prod-price">$89.95</div>
            <span class="inventory-status">In Stock (5 Available)</span>
        </div>
        """
        initial_selectors = {
            "title": ".missing-1",
            "price": ".missing-2",
            "stock_status": ".missing-3",
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="metrics-quality-test",
        )

        self.assertTrue(result.repaired)
        self.assertTrue(result.verified)
        self.assertEqual(result.records_before, 0)
        self.assertEqual(result.records_after, 1)
        self.assertGreater(result.duration_ms, 0.0)
        self.assertGreaterEqual(result.overall_confidence, 0.75)

        # Quality metrics check
        quality = result.data_quality
        self.assertEqual(quality["total_records"], 1)
        self.assertEqual(quality["valid_records"], 1)
        self.assertEqual(quality["invalid_records"], 0)
        self.assertEqual(quality["title_completeness"], 100.0)
        self.assertEqual(quality["price_completeness"], 100.0)
        self.assertEqual(quality["stock_completeness"], 100.0)
        self.assertEqual(quality["overall_quality_score"], 100.0)

    def test_candidate_ranking_and_reasoning_exposure(self):
        """
        Prove that candidates per field are ranked, structured, and expose machine reasoning.
        """
        html = """
        <div class="product-card">
            <h2 class="primary-heading">Mechanical Gaming Keyboard</h2>
            <div class="price_color_tag">$129.99</div>
            <span class="in-stock-label">In Stock</span>
        </div>
        """
        candidates = self.manager.dom_analyzer.analyze(html)
        repair_engine = SelectorRepairEngine()
        price_repair = repair_engine.propose_repair(
            field="price",
            old_selector=".old-price",
            candidates=candidates,
        )

        self.assertGreaterEqual(len(price_repair.candidates), 1)
        selected_candidate = [c for c in price_repair.candidates if c.get("selected")]
        self.assertEqual(len(selected_candidate), 1)
        self.assertIn("reasoning", price_repair.candidates[0])
        self.assertGreaterEqual(price_repair.candidates[0]["confidence"], 0.75)

    def test_adaptive_mutation_id_introduced(self):
        """
        Prove repair when class is removed and element ID is introduced.
        """
        html = """
        <div>
            <h2 id="item-title-id">Studio Monitor Speakers</h2>
            <span id="item-cost-id">$349.00</span>
            <span id="item-stock-id">In Stock</span>
        </div>
        """
        initial_selectors = {
            "title": ".old-class-title",
            "price": ".old-class-price",
            "stock_status": ".old-class-status",
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="id-mutation-test",
        )

        self.assertTrue(result.repaired)
        self.assertEqual(result.data[0]["title"], "Studio Monitor Speakers")
        self.assertEqual(result.data[0]["price"], "$349.00")
        self.assertEqual(result.data[0]["stock_status"], "In Stock")

    def test_phase3_failure_classification_and_summary(self):
        """
        Prove that failure classification and before->healing->after recovery summary
        are populated with structured evidence-based diagnostics.
        """
        html = """
        <div class="product-item">
            <h2 class="title-alpha">Ergonomic Office Chair</h2>
            <div class="cost-value-x9">$199.99</div>
            <span class="stock-status-tag">In Stock</span>
        </div>
        """
        initial_selectors = {
            "title": ".missing-title",
            "price": ".missing-price",
            "stock_status": ".stock-status-tag",
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="phase3-summary-test",
        )

        self.assertTrue(result.repaired)
        self.assertIn("failure_classification", result.model_dump())
        self.assertIn("recovery_summary", result.model_dump())

        # Verify Failure Classification
        classification = result.failure_classification
        self.assertEqual(classification["failure_type"], "DOMChanged")
        self.assertEqual(classification["recoverability"], "recoverable")
        self.assertIn("price", classification["affected_fields"])
        self.assertIn("title", classification["affected_fields"])
        self.assertGreaterEqual(classification["confidence"], 0.75)

        # Verify Recovery Summary
        summary = result.recovery_summary
        self.assertIn("before", summary)
        self.assertIn("healing", summary)
        self.assertIn("after", summary)

        self.assertEqual(summary["before"]["records_extracted"], 0)
        self.assertEqual(set(summary["before"]["broken_fields"]), {"title", "price"})
        self.assertEqual(summary["after"]["records_extracted"], 1)
        self.assertTrue(summary["after"]["verified"])
        self.assertEqual(summary["after"]["validation_status"], "passed")

    def test_phase3_cross_site_data_testid_mutation(self):
        """
        Prove cross-site adaptiveness with data-testid attributes and custom classes.
        """
        html = """
        <div class="product-wrapper">
            <div data-testid="title" class="custom-title-node">Mechanical Keyboard RGB</div>
            <span data-testid="price" class="custom-val-node">$149.95</span>
            <span data-testid="stock" class="custom-avail-node">In Stock (3 Left)</span>
        </div>
        """
        initial_selectors = {
            "title": ".non-existent-t",
            "price": ".non-existent-p",
            "stock_status": ".non-existent-s",
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="data-testid-test",
        )

        self.assertTrue(result.repaired)
        self.assertEqual(result.data[0]["title"], "Mechanical Keyboard RGB")
        self.assertEqual(result.data[0]["price"], "$149.95")
        self.assertEqual(result.data[0]["stock_status"], "In Stock")


class TestPhase4AttackSuite(unittest.TestCase):
    """
    Phase 4 Hackathon Attack Test Suite.
    Proves robustness across unseen DOMs, partial failures, ambiguous markup,
    malformed data types, non-ecommerce pages, table structures, and bounded retries.
    """

    def setUp(self):
        self.manager = HealingManager(max_retries=3)

    def test_attack_1_unseen_dom_zero_demo_keywords(self):
        """
        Attack 1: DOM with zero occurrences of demo keywords (title, name, price, status, availability).
        Tests: tag changes, nesting, and data-testid attributes.
        """
        html = """
        <section class="catalog-grid">
            <article class="item-box">
                <header class="item-header">
                    <h4 class="goods-headline"><a href="/item/101">Wireless Noise-Canceling Headphones</a></h4>
                </header>
                <div class="financials">
                    <span class="currency-tag">$279.50</span>
                </div>
                <div class="inventory-indicator">
                    <span class="in-stock-badge">In Stock (Available Now)</span>
                </div>
            </article>
        </section>
        """
        # Ensure 0 occurrences of demo keywords in fixture
        for kw in ["product-title", "product-name", "product-price", "current-price", "product-status", "availability"]:
            self.assertNotIn(kw, html)

        initial_selectors = {
            "title": ".obsolete-head",
            "price": ".obsolete-cost",
            "stock_status": ".obsolete-inventory",
        }

        result = self.manager.heal_html(
            html_content=html,
            initial_selectors=initial_selectors,
            scraper_id="attack-unseen-dom",
        )

        self.assertTrue(result.repaired)
        self.assertTrue(result.verified)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["title"], "Wireless Noise-Canceling Headphones")
        self.assertEqual(result.data[0]["price"], "$279.50")
        self.assertEqual(result.data[0]["stock_status"], "In Stock")
        self.assertEqual(set(result.fields_repaired), {"title", "price", "stock_status"})

    def test_attack_2_partial_failure_isolation(self):
        """
        Attack 2: Verify that when only title and price break, stock is preserved,
        and when only price and stock break, title is preserved.
        """
        html = """
        <div class="card-entry">
            <h2 class="title-alpha">UltraWide IPS Monitor 34-inch</h2>
            <div class="cost-x9">$499.00</div>
            <span class="stock-active">In Stock</span>
        </div>
        """
        # Scenario A: Only price and stock break, title is valid
        selectors_a = {
            "title": ".title-alpha",
            "price": ".broken-price",
            "stock_status": ".broken-stock",
        }
        result_a = self.manager.heal_html(html_content=html, initial_selectors=selectors_a)
        self.assertTrue(result_a.repaired)
        self.assertIn("price", result_a.fields_repaired)
        self.assertIn("stock_status", result_a.fields_repaired)
        self.assertNotIn("title", result_a.fields_repaired)

        # Scenario B: Only title breaks, price and stock are valid
        selectors_b = {
            "title": ".broken-title",
            "price": ".cost-x9",
            "stock_status": ".stock-active",
        }
        result_b = self.manager.heal_html(html_content=html, initial_selectors=selectors_b)
        self.assertTrue(result_b.repaired)
        self.assertEqual(result_b.fields_repaired, ["title"])

    def test_attack_3_ambiguous_dom_safe_failure(self):
        """
        Attack 3: Intentionally ambiguous HTML without semantic indicators.
        System must trigger safe failure (ambiguous_unsafe) rather than guess.
        """
        html = """
        <div>
            <div>$10.00</div>
            <div>$20.00</div>
            <div>$30.00</div>
        </div>
        """
        initial_selectors = {
            "title": ".non-existent-title",
            "price": ".non-existent-price",
            "stock_status": ".non-existent-stock",
        }
        result = self.manager.heal_html(html_content=html, initial_selectors=initial_selectors)
        self.assertFalse(result.repaired)
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_classification.get("recoverability"), "ambiguous_unsafe")

    def test_attack_4_wrong_data_type_rejection(self):
        """
        Attack 4: Element looks like price class but contains non-numeric text.
        Contract validation must reject it and not report successful recovery.
        """
        html = """
        <div class="item">
            <h2 class="item-title">Smart Thermostat</h2>
            <div class="item-price">hello world not a number</div>
            <span class="item-stock">In Stock</span>
        </div>
        """
        initial_selectors = {
            "title": ".item-title",
            "price": ".missing-price",
            "stock_status": ".item-stock",
        }
        result = self.manager.heal_html(html_content=html, initial_selectors=initial_selectors)
        # Because .item-price has no numeric digits, it fails price validation
        self.assertFalse(result.repaired)
        self.assertFalse(result.verified)

    def test_attack_5_empty_dom_safe_failure(self):
        """
        Attack 5: Empty HTML markup.
        Must return safe failure without crashing or inventing selectors.
        """
        html = "<html><body></body></html>"
        initial_selectors = {
            "title": ".title",
            "price": ".price",
            "stock_status": ".stock",
        }
        result = self.manager.heal_html(html_content=html, initial_selectors=initial_selectors)
        self.assertFalse(result.repaired)
        self.assertFalse(result.verified)
        self.assertEqual(result.records_after, 0)

    def test_attack_6_non_ecommerce_article_page(self):
        """
        Attack 6: Blog article page with no prices or stock indicators.
        Must classify as ambiguous_unsafe / unsupported and safely fail.
        """
        html = """
        <article class="blog-post">
            <h1 class="post-title">10 Tips for Better Web Scraping Architecture</h1>
            <p class="post-content">Web scraping requires careful consideration of rate limiting and DOM changes.</p>
            <footer class="post-meta">Published by Engineering Team</footer>
        </article>
        """
        initial_selectors = {
            "title": ".missing-t",
            "price": ".missing-p",
            "stock_status": ".missing-s",
        }
        result = self.manager.heal_html(html_content=html, initial_selectors=initial_selectors)
        self.assertFalse(result.repaired)
        self.assertFalse(result.verified)

    def test_attack_7_cross_site_table_based_catalog(self):
        """
        Attack 7: Table-based e-commerce product listing.
        Proves autonomous recovery on table <tr> / <td> structures.
        """
        html = """
        <table class="products-table">
            <thead><tr><th>Product</th><th>Price</th><th>Availability</th></tr></thead>
            <tbody>
                <tr class="table-row-item">
                    <td class="item-name-cell">Compact Mechanical Keyboard 60%</td>
                    <td class="item-price-cell">$89.99</td>
                    <td class="item-status-cell">In Stock</td>
                </tr>
            </tbody>
        </table>
        """
        initial_selectors = {
            "title": ".old-tbl-title",
            "price": ".old-tbl-price",
            "stock_status": ".old-tbl-stock",
        }
        result = self.manager.heal_html(html_content=html, initial_selectors=initial_selectors)
        self.assertTrue(result.repaired)
        self.assertTrue(result.verified)
        self.assertEqual(result.data[0]["title"], "Compact Mechanical Keyboard 60%")
        self.assertEqual(result.data[0]["price"], "$89.99")
        self.assertEqual(result.data[0]["stock_status"], "In Stock")

    def test_attack_8_retry_boundary_strict_limit(self):
        """
        Attack 8: Ensure healing retry loop strictly bounds execution and terminates.
        """
        manager = HealingManager(max_retries=2)
        html = "<div>Unresolvable</div>"
        initial_selectors = {"title": ".x", "price": ".y", "stock_status": ".z"}
        result = manager.heal_html(html_content=html, initial_selectors=initial_selectors)
        self.assertFalse(result.repaired)
        self.assertLessEqual(len(result.attempts), 2)


class TestDemoFlowLifecycle(unittest.TestCase):
    """
    Automated verification of the end-to-end hackathon demo lifecycle:
    Normal Scrape -> Simulate Failure -> Failed Scrape -> Self-Healing Recovery -> Recovered Scrape.
    """

    def setUp(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.scraper.state import runtime_state

        self.client = TestClient(app)
        self.runtime_state = runtime_state
        self.runtime_state.reset()

    def tearDown(self):
        self.runtime_state.reset()

    def test_demo_lifecycle_full_sequence(self):
        """
        Test 1: Normal scrape succeeds.
        Test 2: After simulation, scrape reports failure/0 records.
        Test 3: Self-healing after simulation recovers records.
        Test 4: Recovered selectors are dynamically discovered.
        Test 5: After recovery, normal scraping works again.
        Test 6: Simulation does not mutate persistent settings or live collector IDs.
        """
        # Step 1: Normal scrape
        resp1 = self.client.get("/api/scrape")
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertEqual(data1["status"], "success")
        self.assertGreater(data1["records_extracted"], 0)

        # Step 2: Trigger Simulated Failure
        sim_resp = self.client.post("/api/healing/simulate-failure")
        self.assertEqual(sim_resp.status_code, 200)
        sim_data = sim_resp.json()
        self.assertEqual(sim_data["status"], "failed")
        self.assertTrue(sim_data["simulation_active"])
        self.assertEqual(sim_data["records_extracted"], 0)

        # Step 2b: Subsequent scrape MUST fail while simulation is active
        scrape_fail_resp = self.client.get("/api/scrape")
        self.assertEqual(scrape_fail_resp.status_code, 200)
        fail_data = scrape_fail_resp.json()
        self.assertEqual(fail_data["status"], "failed")
        self.assertEqual(fail_data["records_extracted"], 0)
        self.assertIn("SelectorNotFound", fail_data["error"])

        # Step 3 & 4: Self-Healing Recovery discovers replacements and patches runtime state
        recover_resp = self.client.post("/api/healing/recover")
        self.assertEqual(recover_resp.status_code, 200)
        rec_data = recover_resp.json()
        self.assertTrue(rec_data["repaired"])
        self.assertTrue(rec_data["validation_result"])
        self.assertEqual(rec_data["overall_status"], "FULLY HEALED")
        self.assertGreater(rec_data["records_after"], 0)

        # Step 5: After recovery, normal scrape works again
        fresh_scrape = self.client.get("/api/scrape")
        self.assertEqual(fresh_scrape.status_code, 200)
        fresh_data = fresh_scrape.json()
        self.assertEqual(fresh_data["status"], "success")
        self.assertGreater(fresh_data["records_extracted"], 0)

        # Step 6: Settings and collector configurations remain intact
        status_resp = self.client.get("/api/healing/status")
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertIn("collector_id", status_data)
        self.assertEqual(status_data["confidence_threshold"], 0.75)


if __name__ == "__main__":
    unittest.main()






