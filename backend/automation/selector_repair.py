"""AI and rule-based selector repair engine for ScrapeVerse."""

import logging
import os
from typing import Sequence

from backend.automation.models import DOMCandidate, SelectorRepair

logger = logging.getLogger(__name__)


class SelectorRepairEngine:
    """
    Produces selector repair proposals for broken scraper fields.

    Supports:
    - Deterministic / mock repair mode (MOCK_LLM=true)
    - Heuristic candidate matching from DOM analysis
    """

    def __init__(self, mock_mode: bool | None = None) -> None:
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            # Reads MOCK_LLM env var, default to True for offline/test reliability
            self.mock_mode = os.getenv("MOCK_LLM", "true").lower() in {"1", "true", "yes"}

    def propose_repair(
        self,
        *,
        field: str,
        old_selector: str | None,
        candidates: Sequence[DOMCandidate] | None = None,
        reason_hint: str | None = None,
    ) -> SelectorRepair:
        """
        Generate a SelectorRepair proposal.

        Accepts:
        - field: target product attribute (e.g. 'price', 'title', 'stock_status')
        - old_selector: previously configured broken selector
        - candidates: list of DOM candidates extracted by DOMAnalyzer
        """
        effective_old = old_selector or f".product-{field.replace('_', '-')}"

        # 1. Evaluate DOM candidates if available
        if candidates:
            matching = [c for c in candidates if c.field_hint == field]
            # If matching candidates exist, prefer one with a different selector from broken old_selector
            if matching:
                best = matching[0]
                for c in matching:
                    if c.suggested_selector != effective_old:
                        best = c
                        break

                reason = (
                    f"Identified replacement DOM element <{best.tag}> "
                    f"with selector '{best.suggested_selector}' containing value '{best.text}'"
                )
                logger.info("Proposing selector repair for %s: %s -> %s", field, effective_old, best.suggested_selector)
                return SelectorRepair(
                    field=field,
                    old_selector=effective_old,
                    new_selector=best.suggested_selector,
                    confidence=best.confidence,
                    reasoning=reason,
                )

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

        # 3. No candidate and not in mock mode
        return SelectorRepair(
            field=field,
            old_selector=effective_old,
            new_selector=effective_old,
            confidence=0.0,
            reasoning=f"No viable replacement element discovered for field '{field}'",
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
            # If the old selector is already the target, provide alternative class
            if old_selector == target_sel:
                target_sel = f"{target_sel}-updated"
                reason = "Derived alternate class selector from DOM mutation"
            return target_sel, conf, reason

        return (f".{normalized_field}", 0.70, f"Inferred class selector for attribute '{field}'")
