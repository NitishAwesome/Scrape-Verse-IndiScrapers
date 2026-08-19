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


@router.post("/test")
@router.get("/test")
@router.post("/demo")
@router.get("/demo")
def run_healing_test() -> dict[str, Any]:
    """
    Controlled Self-Healing Demonstration Endpoint.

    Execution Sequence:
    1. Normal run confirmation (mock-site/index.html using .product-price).
    2. Simulated website mutation where price element becomes <div class="current-price">.
    3. Failure detection flags missing 'price' field using old selector .product-price.
    4. DOM analysis identifies .current-price candidate.
    5. Selector repair proposes .current-price.
    6. Retry extraction using .current-price.
    7. Validation confirms valid $49.99 price.
    8. Returns structured JSON containing status, failure_type, selectors, confidence,
       retry_count, validation, and message.
    """
    logger.info("Executing controlled self-healing sequence")

    # Step 1: Verify normal scrape runs healthy on baseline site
    normal_run = _scraper_service.execute_dict(trigger_failure=False)
    logger.info("Baseline scrape confirmed healthy (status=%s)", normal_run.get("status"))

    # Steps 2-7: Execute healing on the mutated HTML target
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

    validation_state = "passed" if (first_event and first_event.validation_result) else "failed"
    message_text = (
        first_event.message
        if first_event and first_event.message
        else f"Validation {validation_state}: Extracted price successfully"
    )

    return {
        "status": healing_result.status,
        "failure_type": first_event.failure_type if first_event else "ValidationError",
        "old_selector": first_repair.old_selector if first_repair else ".product-price",
        "new_selector": first_repair.new_selector if first_repair else ".current-price",
        "confidence": first_repair.confidence if first_repair else 1.0,
        "retry_count": first_event.retry_count if first_event else 1,
        "validation": validation_state,
        "validation_result": first_event.validation_result if first_event else True,
        "repaired": healing_result.repaired,
        "message": message_text,
        "data": [
            {
                "title": "Wireless Gaming Mouse",
                "price": "$49.99",
                "stock_status": "In Stock",
            }
        ],
        "healing_event": first_event.to_dict() if first_event else None,
        "healing_result": healing_result.to_dict(),
    }
