"""Runtime extraction state and configuration management for ScrapeGuard."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SELECTORS = {
    "title": ".product-title",
    "price": ".product-price",
    "stock_status": ".product-status",
}

DEMO_MUTATED_SELECTORS = {
    "title": ".product-name",
    "price": ".current-price",
    "stock_status": ".availability",
}


class RuntimeExtractionState:
    """
    Maintains the runtime extraction selector configuration and simulation state.

    Allows deterministic mutation for controlled failure simulations, followed by
    autonomous patching upon successful self-healing recovery.
    """

    def __init__(self) -> None:
        self.original_selectors: dict[str, str] = dict(DEFAULT_SELECTORS)
        self.active_selectors: dict[str, str] = dict(DEFAULT_SELECTORS)
        self.repaired_selectors: dict[str, str] = {}
        self.simulation_active: bool = False
        self.broken_fields: list[str] = []

    def simulate_failure(
        self,
        mutated_selectors: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Activate controlled simulation by invalidating the active extraction selectors."""
        self.simulation_active = True
        self.active_selectors = dict(mutated_selectors or DEMO_MUTATED_SELECTORS)
        self.broken_fields = list(self.active_selectors.keys())
        logger.info(
            "Controlled failure simulation activated. Active selectors mutated to: %s",
            self.active_selectors,
        )
        return self.active_selectors

    def heal(self, repaired_selectors: dict[str, str]) -> None:
        """Apply newly discovered selectors to runtime configuration and clear failure state."""
        self.active_selectors.update(repaired_selectors)
        self.repaired_selectors = dict(repaired_selectors)
        self.simulation_active = False
        self.broken_fields = []
        logger.info(
            "Runtime extraction configuration healed with selectors: %s",
            self.active_selectors,
        )

    def reset(self) -> None:
        """Reset active selectors back to original baseline configuration."""
        self.active_selectors = dict(self.original_selectors)
        self.repaired_selectors = {}
        self.simulation_active = False
        self.broken_fields = []
        logger.info("Runtime extraction configuration reset to baseline: %s", self.active_selectors)

    def is_healthy(self) -> bool:
        """Return True if scraper is in healthy operating state."""
        return not self.simulation_active

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_active": self.simulation_active,
            "active_selectors": self.active_selectors,
            "original_selectors": self.original_selectors,
            "repaired_selectors": self.repaired_selectors,
            "broken_fields": self.broken_fields,
        }


# Global singleton instance shared across scraper and automation routers
runtime_state = RuntimeExtractionState()
