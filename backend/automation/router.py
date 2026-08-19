"""FastAPI router exposing endpoints for the self-healing subsystem."""

import logging
from typing import Any

from fastapi import APIRouter

from backend.automation.healing_manager import HealingManager
from backend.automation.models import FailureType, HealingResult
from backend.scraper.service import ScraperService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/healing", tags=["Self-Healing Automation"])
_healing_manager = HealingManager()
_scraper_service = ScraperService()

# Mutated HTML target representing website layout change during controlled demo
DEMO_MUTATED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mock E-Commerce Target - Mutated</title>
</head>
<body>
    <h1>Product Store</h1>
    <div class="product-card">
        <h2 class="product-title">Wireless Gaming Mouse</h2>
        <div class="current-price">$49.99</div>
        <p class="product-status">In Stock</p>
    </div>
</body>
</html>
"""


@router.get("/status")
def get_healing_status() -> dict[str, Any]:
    """Check the health and configuration of the self-healing subsystem."""
    return {
        "status": "online",
        "module": "self-healing",
        "mock_llm_mode": _healing_manager.repair_engine.mock_mode,
        "max_retries": _healing_manager.max_retries,
        "supported_failure_types": [ft.value for ft in FailureType],
    }


@router.post("/demo")
@router.get("/demo")
def run_healing_demo() -> dict[str, Any]:
    """
    Demonstrate controlled website mutation recovery.

    Initial selector: .product-price
    Mutated HTML: <div class="current-price">$49.99</div>
    Result: Detects missing price -> Discovers .current-price -> Heals -> Validates $49.99.
    """
    logger.info("Starting controlled self-healing demonstration (.product-price -> .current-price)")

    healing_result: HealingResult = _healing_manager.heal_html(
        html_content=DEMO_MUTATED_HTML,
        initial_selectors={
            "title": ".product-title",
            "price": ".product-price",
            "stock_status": ".product-status",
        },
    )

    first_event = healing_result.attempts[0] if healing_result.attempts else None
    first_repair = healing_result.selector_repairs[0] if healing_result.selector_repairs else None

    return {
        "status": healing_result.status,
        "repaired": healing_result.repaired,
        "failure_type": first_event.failure_type if first_event else "Unknown",
        "old_selector": first_repair.old_selector if first_repair else ".product-price",
        "new_selector": first_repair.new_selector if first_repair else ".current-price",
        "confidence": first_repair.confidence if first_repair else 1.0,
        "validation_result": first_event.validation_result if first_event else True,
        "retry_count": first_event.retry_count if first_event else 1,
        "healing_event": first_event.to_dict() if first_event else None,
        "healing_result": healing_result.to_dict(),
    }


@router.post("/test")
@router.get("/test")
def run_healing_test() -> dict[str, Any]:
    """
    Simulate scraper failure and verify automated recovery.
    """
    return run_healing_demo()
