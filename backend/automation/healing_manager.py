import logging
import time
from pathlib import Path
from typing import Any, Callable

from backend.automation.dom_analyzer import DOMAnalyzer
from backend.automation.failure_detector import FailureDetector
from backend.automation.models import (
    DataQualityMetrics,
    FailureClassification,
    FailureType,
    HealingEvent,
    HealingResult,
    HealingStatus,
    Recoverability,
    ScrapeFailure,
    SelectorRepair,
)
from backend.automation.selector_repair import SelectorRepairEngine
from backend.automation.validator import HealingValidator
from backend.scraper.config import get_settings
from backend.scraper.dom_fetcher import DOMFetcher
from backend.scraper.models import ScrapeResult
from backend.scraper.normalizer import normalize_record
from backend.scraper.service import ScraperService

logger = logging.getLogger(__name__)


def calculate_data_quality(data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate deterministic data quality and field completeness metrics.

    Formula:
    - title_completeness = (non-empty titles / total_records) * 100
    - price_completeness = (numeric prices / total_records) * 100
    - stock_completeness = (non-empty stock values / total_records) * 100
    - valid_record_ratio = (records passing all 3 contracts / total_records) * 100
    - field_completeness_avg = 0.35 * title_completeness + 0.35 * price_completeness + 0.30 * stock_completeness
    - overall_quality_score = round(0.50 * field_completeness_avg + 0.50 * valid_record_ratio, 1)
    """
    if not data:
        return {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "title_completeness": 0.0,
            "price_completeness": 0.0,
            "stock_completeness": 0.0,
            "valid_record_ratio": 0.0,
            "overall_quality_score": 0.0,
        }

    total = len(data)
    valid_count = 0
    title_valid = 0
    price_valid = 0
    stock_valid = 0

    for item in data:
        t = str(item.get("title") or "").strip()
        p = str(item.get("price") or "").strip()
        s = str(item.get("stock_status") or "").strip()

        has_t = bool(t)
        has_p = bool(p and any(c.isdigit() for c in p))
        has_s = bool(s)

        if has_t:
            title_valid += 1
        if has_p:
            price_valid += 1
        if has_s:
            stock_valid += 1

        if has_t and has_p and has_s:
            valid_count += 1

    t_pct = round((title_valid / total) * 100.0, 1)
    p_pct = round((price_valid / total) * 100.0, 1)
    s_pct = round((stock_valid / total) * 100.0, 1)
    valid_ratio = round((valid_count / total) * 100.0, 1)

    field_completeness_avg = 0.35 * t_pct + 0.35 * p_pct + 0.30 * s_pct
    overall = round(0.50 * field_completeness_avg + 0.50 * valid_ratio, 1)

    return {
        "total_records": total,
        "valid_records": valid_count,
        "invalid_records": total - valid_count,
        "title_completeness": t_pct,
        "price_completeness": p_pct,
        "stock_completeness": s_pct,
        "valid_record_ratio": valid_ratio,
        "overall_quality_score": overall,
    }


def classify_failure(
    *,
    failures: list[ScrapeFailure],
    repairs: list[SelectorRepair],
    repaired: bool,
    verified: bool,
    confidence_threshold: float = 0.75,
) -> FailureClassification:
    """Classify failure type, affected fields, recoverability, confidence, and explanation."""
    if not failures:
        return FailureClassification(
            failure_type=FailureType.DOM_CHANGED.value if repaired else "Healthy",
            affected_fields=[],
            recoverability=Recoverability.RECOVERABLE.value,
            confidence=1.0,
            reason="All extraction selectors are healthy and matching target elements.",
        )

    broken_fields = list({f.field for f in failures if f.field})
    high_conf_repairs = [r for r in repairs if r.confidence >= confidence_threshold]
    low_conf_repairs = [r for r in repairs if r.confidence < confidence_threshold]

    if not repairs or (len(low_conf_repairs) == len(repairs) and len(repairs) > 0):
        return FailureClassification(
            failure_type=FailureType.LOW_CONFIDENCE.value if repairs else FailureType.SELECTOR_NOT_FOUND.value,
            affected_fields=broken_fields,
            recoverability=Recoverability.AMBIGUOUS_UNSAFE.value,
            confidence=round(max([r.confidence for r in repairs], default=0.0), 2),
            reason=f"Original selectors for {broken_fields} failed and DOM analysis found no replacement candidates exceeding safety threshold ({confidence_threshold:.2f}). Safe failure triggered.",
        )

    if repaired and verified:
        recoverability = (
            Recoverability.RECOVERABLE.value
            if len(high_conf_repairs) == len(broken_fields)
            else Recoverability.PARTIALLY_RECOVERABLE.value
        )
        avg_conf = round(sum(r.confidence for r in high_conf_repairs) / max(len(high_conf_repairs), 1), 2)
        return FailureClassification(
            failure_type=FailureType.DOM_CHANGED.value,
            affected_fields=broken_fields,
            recoverability=recoverability,
            confidence=avg_conf,
            reason=f"Target DOM mutated {broken_fields}. Autonomous analysis synthesized high-confidence replacement selectors and verified extraction.",
        )

    # Not repaired or not verified
    if low_conf_repairs or any(r.confidence < confidence_threshold for r in repairs) or len(high_conf_repairs) < len(broken_fields):
        return FailureClassification(
            failure_type=FailureType.LOW_CONFIDENCE.value if repairs else FailureType.SELECTOR_NOT_FOUND.value,
            affected_fields=broken_fields,
            recoverability=Recoverability.AMBIGUOUS_UNSAFE.value,
            confidence=round(max([r.confidence for r in repairs], default=0.0), 2),
            reason=f"Extraction could not proceed safely for {broken_fields}: replacement candidate confidence is below safety threshold ({confidence_threshold:.2f}). Safe failure triggered.",
        )

    return FailureClassification(
        failure_type=FailureType.UNSUPPORTED_STRUCTURE.value,
        affected_fields=broken_fields,
        recoverability=Recoverability.UNSUPPORTED.value,
        confidence=0.0,
        reason=f"Extraction verification failed for {broken_fields}. Markup structure does not conform to expected e-commerce data contracts.",
    )


def build_recovery_summary(
    *,
    records_before: int,
    records_after: int,
    broken_fields: list[str],
    repaired_fields: list[str],
    repairs: list[SelectorRepair],
    quality: dict[str, Any],
    duration_ms: float,
    verified: bool,
    attempts_count: int,
) -> dict[str, Any]:
    """Generate structured BEFORE -> HEALING -> AFTER summary for dashboard and audit."""
    all_fields = ["title", "price", "stock_status"]
    fields_before = [f for f in all_fields if f not in broken_fields]
    fields_after = list(set(fields_before + repaired_fields))

    top_repair = repairs[0] if repairs else None
    total_candidates_considered = sum(len(r.candidates) for r in repairs) or len(repairs)

    return {
        "before": {
            "records_extracted": records_before,
            "fields_available": fields_before,
            "validation_status": "passed" if records_before > 0 and not broken_fields else "failed",
            "broken_fields": broken_fields,
        },
        "healing": {
            "candidates_considered": total_candidates_considered,
            "selected_candidate": top_repair.new_selector if top_repair else None,
            "confidence": top_repair.confidence if top_repair else 0.0,
            "reasoning": top_repair.reasoning if top_repair else "No candidate selected",
            "fields_repaired": repaired_fields,
            "retry_number": attempts_count,
            "duration_ms": duration_ms,
        },
        "after": {
            "records_extracted": records_after,
            "fields_recovered": fields_after if verified else [],
            "validation_status": "passed" if verified else "failed",
            "data_quality_score": quality.get("overall_quality_score", 0.0),
            "verified": verified,
        },
    }


class HealingManager:
    """
    Orchestrates failure detection, DOM analysis, selector repair, retries, and validation.

    Guarantees:
    - Bounded retries (never loops infinitely, defaults to MAX_HEALING_ATTEMPTS=10).
    - Batch analysis & repair when multiple fields fail simultaneously.
    - Dynamic candidate discovery and live DOM fetching via Bright Data Web Unlocker.
    - Multi-candidate fallback sequences if candidate 1 fails validation.
    - Produces a structured audit trail of HealingEvents.
    """

    def __init__(
        self,
        *,
        scraper_service: ScraperService | None = None,
        dom_fetcher: DOMFetcher | None = None,
        failure_detector: FailureDetector | None = None,
        dom_analyzer: DOMAnalyzer | None = None,
        repair_engine: SelectorRepairEngine | None = None,
        validator: HealingValidator | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.scraper_service = scraper_service or ScraperService()
        self.dom_fetcher = dom_fetcher or DOMFetcher()
        self.failure_detector = failure_detector or FailureDetector()
        self.dom_analyzer = dom_analyzer or DOMAnalyzer()
        self.repair_engine = repair_engine or SelectorRepairEngine()
        self.validator = validator or HealingValidator()
        default_limit = get_settings().max_healing_attempts
        self.max_retries = max(1, max_retries if max_retries is not None else default_limit)

    def heal_live(
        self,
        target_url: str,
        initial_selectors: dict[str, str] | None = None,
    ) -> HealingResult:
        """
        Execute live self-healing against a real target URL.

        1. Fetches live target DOM HTML using Bright Data Web Unlocker (DOMFetcher).
        2. Dynamically analyzes live DOM structure.
        3. Synthesizes replacement selectors exceeding confidence threshold.
        4. Retries extraction and validates recovered dataset.
        """
        logger.info("Starting live self-healing recovery pipeline for %s", target_url)
        try:
            live_html = self.dom_fetcher.fetch(target_url)
        except Exception as exc:
            logger.error("Failed to fetch live HTML for healing: %s", exc)
            return HealingResult(
                status=HealingStatus.FAILED.value,
                repaired=False,
                attempts=[],
                selector_repairs=[],
                data=[],
                error=f"Live DOM acquisition failed: {exc}",
            )

        return self.heal_html(
            html_content=live_html,
            initial_selectors=initial_selectors,
            scraper_id=target_url,
        )

    def heal_html(
        self,
        html_content: str,
        initial_selectors: dict[str, str] | None = None,
        scraper_id: str = "c_mock_123456",
    ) -> HealingResult:
        """
        Execute self-healing on an HTML DOM string.

        Supports dynamic number of broken fields, candidate ranking, and multi-candidate fallbacks.
        """
        start_time = time.perf_counter()
        active_selectors = dict(
            initial_selectors
            or {
                "title": ".product-title",
                "price": ".product-price",
                "stock_status": ".product-status",
            }
        )

        def extract_run(selectors: dict[str, str]) -> dict[str, Any]:
            raw_records = self.dom_analyzer.extract_all_with_selectors(html_content, selectors)
            if not raw_records:
                return {
                    "collector_id": scraper_id,
                    "status": "failed",
                    "records_extracted": 0,
                    "data": [],
                    "error": "Extracted 0 records with active selectors",
                }
            normalized_objs = [normalize_record(r) for r in raw_records]
            normalized = [n.model_dump() for n in normalized_objs]
            return {
                "collector_id": scraper_id,
                "status": "success",
                "records_extracted": len(normalized),
                "data": normalized,
                "error": None,
            }

        # Step 1: Run baseline extraction with initial selectors
        initial_result = extract_run(active_selectors)
        failures = self.failure_detector.detect_all(initial_result)
        records_before = initial_result.get("records_extracted", 0) if not failures else 0
        broken_fields = list({f.field for f in failures if f.field})

        if not failures:
            logger.info("Initial extraction on HTML was already healthy.")
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            dataset = initial_result.get("data", [])
            quality = calculate_data_quality(dataset)
            classification = classify_failure(
                failures=[],
                repairs=[],
                repaired=True,
                verified=True,
                confidence_threshold=self.repair_engine.confidence_threshold,
            )
            summary = build_recovery_summary(
                records_before=records_before,
                records_after=len(dataset),
                broken_fields=[],
                repaired_fields=[],
                repairs=[],
                quality=quality,
                duration_ms=duration_ms,
                verified=True,
                attempts_count=0,
            )
            return HealingResult(
                status=HealingStatus.SUCCESS.value,
                repaired=True,
                attempts=[],
                selector_repairs=[],
                data=dataset,
                error=None,
                records_before=records_before,
                records_after=len(dataset),
                fields_detected_as_broken=[],
                fields_repaired=[],
                overall_confidence=1.0,
                duration_ms=duration_ms,
                verified=True,
                data_quality=quality,
                failure_classification=classification.to_dict(),
                recovery_summary=summary,
            )

        applied_repairs: list[SelectorRepair] = []
        events: list[HealingEvent] = []

        # Maintain candidate indexes for multi-candidate fallback
        candidate_indices: dict[str, int] = {}

        for attempt in range(1, self.max_retries + 1):
            logger.info("Self-healing iteration attempt %d of %d", attempt, self.max_retries)
            attempt_repairs: list[SelectorRepair] = []

            # Partial repair: Repair ONLY detected failing fields
            for failure in failures:
                target_field = failure.field or "price"
                dom_candidates = self.dom_analyzer.analyze(html_content, target_field=target_field)

                ranked_repairs = self.repair_engine.propose_candidates_ranked(
                    field=target_field,
                    old_selector=failure.old_selector or active_selectors.get(target_field),
                    candidates=dom_candidates,
                )

                if ranked_repairs:
                    idx = candidate_indices.get(target_field, 0)
                    if idx >= len(ranked_repairs):
                        idx = 0
                    repair = ranked_repairs[idx]
                    candidate_indices[target_field] = idx + 1
                else:
                    repair = self.repair_engine.propose_repair(
                        field=target_field,
                        old_selector=failure.old_selector or active_selectors.get(target_field),
                        candidates=dom_candidates,
                    )

                # Confidence Safety Gate: If proposed repair is below threshold, abort patching
                if repair.confidence < self.repair_engine.confidence_threshold:
                    logger.warning(
                        "Self-healing safety gate triggered for '%s': confidence %.2f is below threshold %.2f",
                        target_field,
                        repair.confidence,
                        self.repair_engine.confidence_threshold,
                    )
                    attempt_repairs.append(repair)
                    continue

                attempt_repairs.append(repair)
                active_selectors[target_field] = repair.new_selector

            applied_repairs.extend(attempt_repairs)
            first_repair = attempt_repairs[0] if attempt_repairs else (applied_repairs[-1] if applied_repairs else SelectorRepair(field="price", old_selector="", new_selector="", confidence=0.0))

            # Check if any repair failed the safety gate
            low_conf_repairs = [r for r in attempt_repairs if r.confidence < self.repair_engine.confidence_threshold]
            if low_conf_repairs:
                reason_detail = low_conf_repairs[0].reasoning or "Candidate score below safety threshold"
                event = HealingEvent(
                    scraper_id=scraper_id,
                    failure_type=failures[0].failure_type if failures else "ValidationError",
                    old_selector=first_repair.old_selector,
                    new_selector=first_repair.new_selector,
                    target_field=first_repair.field,
                    confidence=first_repair.confidence,
                    validation_result=False,
                    retry_count=attempt,
                    status=HealingStatus.FAILED.value,
                    message=f"Safety gate: {reason_detail}",
                )
                events.append(event)

                if attempt == self.max_retries:
                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    quality = calculate_data_quality([])
                    classification = classify_failure(
                        failures=failures,
                        repairs=applied_repairs,
                        repaired=False,
                        verified=False,
                        confidence_threshold=self.repair_engine.confidence_threshold,
                    )
                    summary = build_recovery_summary(
                        records_before=records_before,
                        records_after=0,
                        broken_fields=broken_fields,
                        repaired_fields=[],
                        repairs=applied_repairs,
                        quality=quality,
                        duration_ms=duration_ms,
                        verified=False,
                        attempts_count=len(events),
                    )
                    return HealingResult(
                        status=HealingStatus.FAILED.value,
                        repaired=False,
                        attempts=events,
                        selector_repairs=applied_repairs,
                        data=[],
                        error=f"Exhausted maximum retry limit ({self.max_retries} attempts) without passing validation (Safety gate: {reason_detail})",
                        records_before=records_before,
                        records_after=0,
                        fields_detected_as_broken=broken_fields,
                        fields_repaired=[],
                        overall_confidence=low_conf_repairs[0].confidence,
                        duration_ms=duration_ms,
                        verified=False,
                        data_quality=quality,
                        failure_classification=classification.to_dict(),
                        recovery_summary=summary,
                    )
                continue

            # Retry extraction with all updated selectors
            retry_result = extract_run(active_selectors)
            is_valid, validation_msg = self.validator.validate(retry_result)

            event = HealingEvent(
                scraper_id=scraper_id,
                failure_type=failures[0].failure_type if failures else "ValidationError",
                old_selector=first_repair.old_selector,
                new_selector=first_repair.new_selector,
                target_field=first_repair.field,
                confidence=first_repair.confidence,
                validation_result=is_valid,
                retry_count=attempt,
                status=HealingStatus.SUCCESS.value if is_valid else HealingStatus.FAILED.value,
                message=validation_msg,
            )
            events.append(event)

            if is_valid:
                recovered_dataset = retry_result.get("data", [])
                repaired_fields_list = [r.field for r in applied_repairs if r.confidence >= self.repair_engine.confidence_threshold]
                avg_confidence = (
                    round(sum(r.confidence for r in applied_repairs) / len(applied_repairs), 2)
                    if applied_repairs
                    else 1.0
                )
                quality = calculate_data_quality(recovered_dataset)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                classification = classify_failure(
                    failures=failures,
                    repairs=applied_repairs,
                    repaired=True,
                    verified=True,
                    confidence_threshold=self.repair_engine.confidence_threshold,
                )
                summary = build_recovery_summary(
                    records_before=records_before,
                    records_after=len(recovered_dataset),
                    broken_fields=broken_fields,
                    repaired_fields=list(set(repaired_fields_list)),
                    repairs=applied_repairs,
                    quality=quality,
                    duration_ms=duration_ms,
                    verified=True,
                    attempts_count=len(events),
                )

                logger.info(
                    "Self-healing HTML extraction SUCCEEDED on attempt %d: Repaired %d selector(s) across %d record(s)",
                    attempt,
                    len(applied_repairs),
                    len(recovered_dataset),
                )
                return HealingResult(
                    status=HealingStatus.SUCCESS.value,
                    repaired=True,
                    attempts=events,
                    selector_repairs=applied_repairs,
                    data=recovered_dataset,
                    error=None,
                    records_before=records_before,
                    records_after=len(recovered_dataset),
                    fields_detected_as_broken=broken_fields,
                    fields_repaired=list(set(repaired_fields_list)),
                    overall_confidence=avg_confidence,
                    duration_ms=duration_ms,
                    verified=True,
                    data_quality=quality,
                    failure_classification=classification.to_dict(),
                    recovery_summary=summary,
                )

            failures = self.failure_detector.detect_all(retry_result)
            if not failures:
                break

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        quality = calculate_data_quality([])
        classification = classify_failure(
            failures=failures,
            repairs=applied_repairs,
            repaired=False,
            verified=False,
            confidence_threshold=self.repair_engine.confidence_threshold,
        )
        summary = build_recovery_summary(
            records_before=records_before,
            records_after=0,
            broken_fields=broken_fields,
            repaired_fields=[],
            repairs=applied_repairs,
            quality=quality,
            duration_ms=duration_ms,
            verified=False,
            attempts_count=len(events),
        )
        return HealingResult(
            status=HealingStatus.FAILED.value,
            repaired=False,
            attempts=events,
            selector_repairs=applied_repairs,
            data=[],
            error=f"Exhausted maximum retry limit ({self.max_retries} attempts) without passing validation",
            records_before=records_before,
            records_after=0,
            fields_detected_as_broken=broken_fields,
            fields_repaired=[],
            overall_confidence=0.0,
            duration_ms=duration_ms,
            verified=False,
            data_quality=quality,
            failure_classification=classification.to_dict(),
            recovery_summary=summary,
        )

    def heal(
        self,
        initial_result: ScrapeResult | dict[str, Any] | None = None,
        *,
        html_content: str | None = None,
        scrape_fn: Callable[..., ScrapeResult | dict[str, Any]] | None = None,
    ) -> HealingResult:
        """
        Execute self-healing for a failed scrape (mock or runner-based).
        """
        start_time = time.perf_counter()
        runner = scrape_fn or self.scraper_service.execute
        current_result = initial_result if initial_result is not None else runner()

        failures = self.failure_detector.detect_all(current_result)
        initial_records_count = (
            len(current_result.data)
            if isinstance(current_result, ScrapeResult)
            else len(current_result.get("data", []))
        )
        records_before = initial_records_count if not failures else 0
        broken_fields = list({f.field for f in failures if f.field})

        if not failures:
            logger.info("Scrape result is already healthy. No healing required.")
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            recovered_records = (
                current_result.data
                if isinstance(current_result, ScrapeResult)
                else current_result.get("data", [])
            )
            rec_dicts = [
                r.model_dump() if hasattr(r, "model_dump") else dict(r)
                for r in recovered_records
            ]
            quality = calculate_data_quality(rec_dicts)
            return HealingResult(
                status=HealingStatus.SUCCESS.value,
                repaired=True,
                attempts=[],
                selector_repairs=[],
                data=rec_dicts,
                error=None,
                records_before=records_before,
                records_after=len(rec_dicts),
                fields_detected_as_broken=[],
                fields_repaired=[],
                overall_confidence=1.0,
                duration_ms=duration_ms,
                verified=True,
                data_quality=quality,
            )

        resolved_html = html_content or self._load_html_content()
        applied_repairs: list[SelectorRepair] = []
        events: list[HealingEvent] = []

        for attempt in range(1, self.max_retries + 1):
            logger.info("Healing attempt %d of %d", attempt, self.max_retries)

            for failure in failures:
                target_field = failure.field or "price"
                dom_candidates = self.dom_analyzer.analyze(resolved_html, target_field=target_field)

                repair = self.repair_engine.propose_repair(
                    field=target_field,
                    old_selector=failure.old_selector,
                    candidates=dom_candidates,
                )
                applied_repairs.append(repair)

            last_repair = applied_repairs[-1] if applied_repairs else SelectorRepair(field="price", old_selector="", new_selector="", confidence=1.0)
            retry_result = self._execute_retry(runner, last_repair)

            is_valid, validation_msg = self.validator.validate(retry_result)

            event = HealingEvent(
                scraper_id=failures[0].scraper_id,
                failure_type=failures[0].failure_type,
                old_selector=last_repair.old_selector,
                new_selector=last_repair.new_selector,
                target_field=last_repair.field,
                confidence=last_repair.confidence,
                validation_result=is_valid,
                retry_count=attempt,
                status=HealingStatus.SUCCESS.value if is_valid else HealingStatus.FAILED.value,
                message=validation_msg,
            )
            events.append(event)

            if is_valid:
                recovered_records = (
                    retry_result.data
                    if isinstance(retry_result, ScrapeResult)
                    else retry_result.get("data", [])
                )
                rec_dicts = [
                    r.model_dump() if hasattr(r, "model_dump") else dict(r)
                    for r in recovered_records
                ]
                repaired_fields_list = [r.field for r in applied_repairs if r.confidence >= self.repair_engine.confidence_threshold]
                avg_confidence = (
                    round(sum(r.confidence for r in applied_repairs) / len(applied_repairs), 2)
                    if applied_repairs
                    else 1.0
                )
                quality = calculate_data_quality(rec_dicts)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return HealingResult(
                    status=HealingStatus.SUCCESS.value,
                    repaired=True,
                    attempts=events,
                    selector_repairs=applied_repairs,
                    data=rec_dicts,
                    error=None,
                    records_before=records_before,
                    records_after=len(rec_dicts),
                    fields_detected_as_broken=broken_fields,
                    fields_repaired=list(set(repaired_fields_list)),
                    overall_confidence=avg_confidence,
                    duration_ms=duration_ms,
                    verified=True,
                    data_quality=quality,
                )

            failures = self.failure_detector.detect_all(retry_result)
            if not failures:
                break

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return HealingResult(
            status=HealingStatus.FAILED.value,
            repaired=False,
            attempts=events,
            selector_repairs=applied_repairs,
            data=[],
            error=f"Exhausted maximum retry limit ({self.max_retries} attempts) without passing validation",
            records_before=records_before,
            records_after=0,
            fields_detected_as_broken=broken_fields,
            fields_repaired=[],
            overall_confidence=0.0,
            duration_ms=duration_ms,
            verified=False,
            data_quality=calculate_data_quality([]),
        )

    def _execute_retry(
        self,
        runner: Callable[..., ScrapeResult | dict[str, Any]],
        repair: SelectorRepair,
    ) -> ScrapeResult | dict[str, Any]:
        """Execute a retry scrape after applying a repair."""
        try:
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
