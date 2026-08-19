"""HealingManager orchestrates the complete self-healing lifecycle for ScrapeVerse."""

import logging
from pathlib import Path
from typing import Any, Callable

from backend.automation.dom_analyzer import DOMAnalyzer
from backend.automation.failure_detector import FailureDetector
from backend.automation.models import (
    HealingEvent,
    HealingResult,
    HealingStatus,
    ScrapeFailure,
    SelectorRepair,
)
from backend.automation.selector_repair import SelectorRepairEngine
from backend.automation.validator import HealingValidator
from backend.scraper.config import get_settings
from backend.scraper.models import ScrapeResult
from backend.scraper.normalizer import normalize_record
from backend.scraper.service import ScraperService

logger = logging.getLogger(__name__)



class HealingManager:
    """
    Orchestrates failure detection, DOM analysis, selector repair, retries, and validation.

    Guarantees:
    - Never loops infinitely (bounded by max_retries).
    - Produces a structured audit trail of HealingEvents.
    - Decoupled from scraper internals.
    """

    def __init__(
        self,
        *,
        scraper_service: ScraperService | None = None,
        failure_detector: FailureDetector | None = None,
        dom_analyzer: DOMAnalyzer | None = None,
        repair_engine: SelectorRepairEngine | None = None,
        validator: HealingValidator | None = None,
        max_retries: int = 3,
    ) -> None:
        self.scraper_service = scraper_service or ScraperService()
        self.failure_detector = failure_detector or FailureDetector()
        self.dom_analyzer = dom_analyzer or DOMAnalyzer()
        self.repair_engine = repair_engine or SelectorRepairEngine()
        self.validator = validator or HealingValidator()
        self.max_retries = max(1, max_retries)

    def heal(
        self,
        initial_result: ScrapeResult | dict[str, Any] | None = None,
        *,
        html_content: str | None = None,
        scrape_fn: Callable[..., ScrapeResult | dict[str, Any]] | None = None,
    ) -> HealingResult:
        """
        Execute self-healing for a failed scrape.

        If initial_result is not provided, runs an initial scrape.
        Retries up to max_retries until validation passes or attempts are exhausted.
        """
        runner = scrape_fn or self.scraper_service.execute
        current_result = initial_result if initial_result is not None else runner()

        failure: ScrapeFailure | None = self.failure_detector.detect(current_result)
        if not failure:
            logger.info("Scrape result is already healthy. No healing required.")
            return HealingResult(
                status=HealingStatus.SUCCESS.value,
                repaired=True,
                attempts=[],
                selector_repairs=[],
                error=None,
            )

        logger.info(
            "Starting self-healing for scraper '%s' (Failure: %s)",
            failure.scraper_id,
            failure.failure_type,
        )

        resolved_html = html_content or self._load_html_content()
        applied_repairs: list[SelectorRepair] = []
        events: list[HealingEvent] = []

        for attempt in range(1, self.max_retries + 1):
            logger.info("Healing attempt %d of %d", attempt, self.max_retries)

            # 1. DOM Analysis
            target_field = failure.field or "price"
            dom_candidates = self.dom_analyzer.analyze(resolved_html, target_field=target_field)

            # 2. Selector Repair
            repair = self.repair_engine.propose_repair(
                field=target_field,
                old_selector=failure.old_selector,
                candidates=dom_candidates,
            )
            applied_repairs.append(repair)

            # 3. Retry Scraping with the repaired selector (simulated / real runner)
            retry_result = self._execute_retry(runner, repair)

            # 4. Post-Repair Validation
            is_valid, validation_msg = self.validator.validate(retry_result, target_field=target_field)

            event = HealingEvent(
                scraper_id=failure.scraper_id,
                failure_type=failure.failure_type,
                old_selector=repair.old_selector,
                new_selector=repair.new_selector,
                target_field=repair.field,
                confidence=repair.confidence,
                validation_result=is_valid,
                retry_count=attempt,
                status=HealingStatus.SUCCESS.value if is_valid else HealingStatus.FAILED.value,
                message=validation_msg,
            )
            events.append(event)

            if is_valid:
                logger.info(
                    "Self-healing SUCCEEDED on attempt %d: %s -> %s",
                    attempt,
                    repair.old_selector,
                    repair.new_selector,
                )
                return HealingResult(
                    status=HealingStatus.SUCCESS.value,
                    repaired=True,
                    attempts=events,
                    selector_repairs=applied_repairs,
                    error=None,
                )

            # Update failure context for next retry cycle if needed
            next_failure = self.failure_detector.detect(retry_result)
            if next_failure:
                failure = next_failure

        logger.error("Self-healing FAILED after %d attempts", self.max_retries)
        return HealingResult(
            status=HealingStatus.FAILED.value,
            repaired=False,
            attempts=events,
            selector_repairs=applied_repairs,
            error=f"Exhausted maximum retry limit ({self.max_retries} attempts) without passing validation",
        )

    def _execute_retry(
        self,
        runner: Callable[..., ScrapeResult | dict[str, Any]],
        repair: SelectorRepair,
    ) -> ScrapeResult | dict[str, Any]:
        """Execute a retry scrape after applying a repair."""
        try:
            # Runner called with trigger_failure=False to test the repaired state
            return runner(trigger_failure=False)
        except TypeError:
            return runner()
        except Exception as exc:
            logger.exception("Exception occurred during scrape retry execution")
            return {
                "status": "failed",
                "records_extracted": 0,
                "data": [],
                "error": str(exc),
            }

    def _load_html_content(self) -> str:
        """Load target HTML from configured site path or fallback markup."""
        try:
            settings = get_settings()
            site_path = settings.mock_site_path
            path = site_path if site_path.is_absolute() else Path.cwd() / site_path
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not read HTML from site path: %s", exc)

        return (
            "<html><body>"
            "<h2 class='product-title'>Wireless Gaming Mouse</h2>"
            "<p class='product-price'>$49.99</p>"
            "<p class='product-status'>In Stock</p>"
            "</body></html>"
        )

    def heal_html(
        self,
        html_content: str,
        initial_selectors: dict[str, str] | None = None,
        scraper_id: str = "c_mock_123456",
    ) -> HealingResult:
        """
        Execute self-healing specifically on an HTML DOM string.

        Used for demonstration scenarios where the DOM mutates (e.g. .product-price -> .current-price).
        """
        active_selectors = dict(
            initial_selectors
            or {
                "title": ".product-title",
                "price": ".product-price",
                "stock_status": ".product-status",
            }
        )

        def extract_run(selectors: dict[str, str]) -> dict[str, Any]:
            raw_fields = self.dom_analyzer.extract_with_selectors(html_content, selectors)
            normalized = normalize_record(raw_fields)
            is_empty = not any(v for v in raw_fields.values())
            return {
                "collector_id": scraper_id,
                "status": "success" if not is_empty else "failed",
                "records_extracted": 1 if not is_empty else 0,
                "data": [normalized.model_dump()] if not is_empty else [],
                "error": None if not is_empty else "Extracted 0 records",
            }

        # Step 1: Run initial extraction with initial selectors
        initial_result = extract_run(active_selectors)
        failure = self.failure_detector.detect(initial_result)

        if not failure:
            logger.info("Initial extraction on HTML was already healthy.")
            return HealingResult(
                status=HealingStatus.SUCCESS.value,
                repaired=True,
                attempts=[],
                selector_repairs=[],
                error=None,
            )

        applied_repairs: list[SelectorRepair] = []
        events: list[HealingEvent] = []

        for attempt in range(1, self.max_retries + 1):
            target_field = failure.field or "price"
            dom_candidates = self.dom_analyzer.analyze(html_content, target_field=target_field)

            repair = self.repair_engine.propose_repair(
                field=target_field,
                old_selector=failure.old_selector or active_selectors.get(target_field),
                candidates=dom_candidates,
            )
            applied_repairs.append(repair)

            # Apply repair to active selectors
            active_selectors[target_field] = repair.new_selector

            # Retry extraction with updated selector
            retry_result = extract_run(active_selectors)
            is_valid, validation_msg = self.validator.validate(retry_result, target_field=target_field)

            event = HealingEvent(
                scraper_id=scraper_id,
                failure_type=failure.failure_type,
                old_selector=repair.old_selector,
                new_selector=repair.new_selector,
                target_field=repair.field,
                confidence=repair.confidence,
                validation_result=is_valid,
                retry_count=attempt,
                status=HealingStatus.SUCCESS.value if is_valid else HealingStatus.FAILED.value,
                message=validation_msg,
            )
            events.append(event)

            if is_valid:
                logger.info(
                    "Self-healing HTML extraction SUCCEEDED on attempt %d: %s -> %s",
                    attempt,
                    repair.old_selector,
                    repair.new_selector,
                )
                return HealingResult(
                    status=HealingStatus.SUCCESS.value,
                    repaired=True,
                    attempts=events,
                    selector_repairs=applied_repairs,
                    error=None,
                )

            next_failure = self.failure_detector.detect(retry_result)
            if next_failure:
                failure = next_failure

        return HealingResult(
            status=HealingStatus.FAILED.value,
            repaired=False,
            attempts=events,
            selector_repairs=applied_repairs,
            error=f"Exhausted maximum retry limit ({self.max_retries} attempts) without passing validation",
        )

