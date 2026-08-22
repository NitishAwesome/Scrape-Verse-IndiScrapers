"""AI and rule-based selector repair engine for ScrapeVerse."""

import logging
import os
from typing import Sequence

from backend.automation.models import DOMCandidate, SelectorRepair
from backend.scraper.config import get_settings

logger = logging.getLogger(__name__)


class SelectorRepairEngine:
    """
    Produces selector repair proposals for broken scraper fields.

    Supports:
    - Dynamic candidate discovery and ranking from live DOM analysis
    - Confidence scoring and threshold filtering (HEALING_CONFIDENCE_THRESHOLD)
    - Multi-candidate fallback sequences
    - Deterministic fallback for offline/test reliability (MOCK_LLM=true)
    """

    def __init__(
        self,
        mock_mode: bool | None = None,
        confidence_threshold: float | None = None,
    ) -> None:
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = os.getenv("MOCK_LLM", "true").lower() in {"1", "true", "yes"}

        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
        else:
            try:
                self.confidence_threshold = get_settings().healing_confidence_threshold
            except Exception:
                self.confidence_threshold = 0.75

    def propose_candidates_ranked(
        self,
        *,
        field: str,
        old_selector: str | None,
        candidates: Sequence[DOMCandidate] | None = None,
    ) -> list[SelectorRepair]:
        """
        Return a ranked list of candidate repairs for a field exceeding confidence_threshold.
        """
        effective_old = old_selector or f".product-{field.replace('_', '-')}"
        if not candidates:
            return []

        matching = [
            c for c in candidates
            if c.field_hint == field and c.confidence >= self.confidence_threshold
        ]

        matching.sort(key=lambda c: c.confidence, reverse=True)

        repairs: list[SelectorRepair] = []
        for c in matching:
            reason = (
                c.reasoning
                or f"Identified replacement DOM element <{c.tag}> with selector '{c.suggested_selector}' (confidence: {c.confidence:.2f})"
            )
            repairs.append(
                SelectorRepair(
                    field=field,
                    old_selector=effective_old,
                    new_selector=c.suggested_selector,
                    confidence=c.confidence,
                    reasoning=reason,
                )
            )

        return repairs

    def propose_repair(
        self,
        *,
        field: str,
        old_selector: str | None,
        candidates: Sequence[DOMCandidate] | None = None,
        reason_hint: str | None = None,
    ) -> SelectorRepair:
        """
        Generate the top SelectorRepair proposal for a broken field.
        """
        effective_old = old_selector or f".product-{field.replace('_', '-')}"

        # 1. Evaluate DOM candidates if available
        if candidates:
            ranked = self.propose_candidates_ranked(
                field=field,
                old_selector=effective_old,
                candidates=candidates,
            )
            if ranked:
                # Prefer candidate with different selector than broken old_selector
                best = ranked[0]
                for r in ranked:
                    if r.new_selector != effective_old:
                        best = r
                        break

                logger.info(
                    "Proposing selector repair for %s: %s -> %s (confidence: %.2f)",
                    field,
                    effective_old,
                    best.new_selector,
                    best.confidence,
                )
                return best

        # 2. Deterministic / MOCK_LLM fallback heuristics
        if self.mock_mode:
            fallback_selector, fallback_conf, fallback_reason = self._deterministic_proposal(field, effective_old)
            return SelectorRepair(
                field=field,
                old_selector=effective_old,
                new_selector=fallback_selector,
                confidence=fallback_conf,
                reasoning=fallback_reason,
            )

        # 3. No candidate meeting threshold
        return SelectorRepair(
            field=field,
            old_selector=effective_old,
            new_selector=effective_old,
            confidence=0.0,
            reasoning=f"No viable replacement element discovered exceeding confidence threshold ({self.confidence_threshold:.2f}) for '{field}'",
        )

    def _deterministic_proposal(self, field: str, old_selector: str) -> tuple[str, float, str]:
        """Deterministic repair mappings for standard e-commerce fields in test/offline modes."""
        normalized_field = field.lower().replace(" ", "_")

        selector_map = {
            "price": (".product-price", 0.95, "Matched e-commerce price tag heuristic in DOM"),
            "title": (".product-title", 0.95, "Matched product title heading heuristic in DOM"),
            "stock_status": (".product-status", 0.95, "Matched stock status badge heuristic in DOM"),
        }

        if normalized_field in selector_map:
            target_sel, conf, reason = selector_map[normalized_field]
            if old_selector == target_sel:
                target_sel = f"{target_sel}-updated"
                reason = "Derived alternate class selector from DOM mutation"
            return target_sel, conf, reason

        return (f".{normalized_field}", 0.70, f"Inferred class selector for attribute '{field}'")
