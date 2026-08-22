"""FastAPI router exposing endpoints for the self-healing subsystem."""

import logging
from typing import Any

from fastapi import APIRouter, Body, Query

from backend.automation.healing_manager import HealingManager
from backend.automation.models import FailureType, HealingResult
from backend.scraper.service import ScraperService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/healing", tags=["Self-Healing Automation"])
_healing_manager = HealingManager()
_scraper_service = ScraperService()

# Single-selector mutated HTML target (.product-price -> .current-price)
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

# Multi-selector mutated HTML target (title, price, and stock changed simultaneously)
DEMO_MULTI_MUTATED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mock E-Commerce Target - Full Redesign</title>
</head>
<body>
    <header class="main-header">
        <div class="store-brand">TechStore Express</div>
    </header>
    <main class="product-container">
        <div class="product-card">
            <h2 class="product-name">Wireless Gaming Mouse</h2>
            <div class="current-price">$49.99</div>
            <p class="availability">In Stock</p>
        </div>
    </main>
</body>
</html>
"""


def get_mutated_catalog_html() -> str:
    """Produce the mutated target HTML representing the website DOM restructuring."""
    try:
        from pathlib import Path
        from backend.scraper.config import get_settings

        site_path = get_settings().mock_site_path
        path = site_path if site_path.is_absolute() else Path.cwd() / site_path
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # Mutate target CSS classes across all product cards
            mutated = content.replace("product-title", "product-name")
            mutated = mutated.replace("product-price", "current-price")
            mutated = mutated.replace("product-status", "availability")
            return mutated
    except Exception as exc:
        logger.warning("Could not mutate catalog from file: %s", exc)

    return DEMO_MULTI_MUTATED_HTML


def _build_unified_payload(
    healing_result: HealingResult,
    initial_selectors: dict[str, str],
) -> dict[str, Any]:
    """Helper to assemble a rich, unified healing response payload."""
    repaired_selectors = dict(initial_selectors)
    repairs_list = []

    final_data = healing_result.data if healing_result.data else []

    field_value_map = {}
    if final_data:
        first_item = final_data[0]
        field_value_map = {
            "title": first_item.get("title", "Extracted Title"),
            "price": first_item.get("price", "$0.00"),
            "stock_status": first_item.get("stock_status", "In Stock"),
        }

    for idx, r in enumerate(healing_result.selector_repairs):
        repaired_selectors[r.field] = r.new_selector
        corresponding_attempt = (
            healing_result.attempts[idx]
            if idx < len(healing_result.attempts)
            else (healing_result.attempts[-1] if healing_result.attempts else None)
        )
        repairs_list.append(
            {
                "field": r.field,
                "old_selector": r.old_selector,
                "new_selector": r.new_selector,
                "confidence": r.confidence,
                "status": "HEALED" if healing_result.repaired else "FAILED",
                "extracted_value": field_value_map.get(r.field, "Extracted Value"),
                "attempt": corresponding_attempt.retry_count if corresponding_attempt else idx + 1,
                "validation_result": corresponding_attempt.validation_result if corresponding_attempt else healing_result.repaired,
                "reasoning": r.reasoning or f"Dynamic DOM candidate matched with {int(r.confidence * 100)}% confidence",
            }
        )

    first_event = healing_result.attempts[0] if healing_result.attempts else None
    first_repair = healing_result.selector_repairs[0] if healing_result.selector_repairs else None
    last_event = healing_result.attempts[-1] if healing_result.attempts else None

    validation_state = "passed" if healing_result.repaired else "failed"
    message_text = (
        last_event.message
        if last_event and last_event.message
        else f"Validation {validation_state}: Extraction verified across {len(final_data)} records"
    )

    failures_count = len(healing_result.selector_repairs) or (1 if not healing_result.repaired else 0)
    selectors_repaired_count = len(healing_result.selector_repairs) if healing_result.repaired else 0

    return {
        "status": healing_result.status,
        "repaired": healing_result.repaired,
        "failures_detected": failures_count,
        "selectors_repaired": selectors_repaired_count,
        "attempts": len(healing_result.attempts),
        "validation": validation_state,
        "validation_result": healing_result.repaired,
        "records_extracted": len(final_data),
        "records_recovered": len(final_data) if healing_result.repaired else 0,
        "overall_status": "FULLY HEALED" if healing_result.repaired else "FAILED",
        "failure_type": first_event.failure_type if first_event else "ValidationError",
        "old_selector": first_repair.old_selector if first_repair else ".product-price",
        "new_selector": first_repair.new_selector if first_repair else ".current-price",
        "confidence": first_repair.confidence if first_repair else 1.0,
        "retry_count": len(healing_result.attempts),
        "message": message_text,
        "original_selectors": initial_selectors,
        "repaired_selectors": repaired_selectors,
        "repairs": repairs_list,
        "data": final_data,
        "final_data": final_data,
        "healing_event": first_event.to_dict() if first_event else None,
        "healing_result": healing_result.to_dict(),
    }


@router.get("/status")
def get_healing_status() -> dict[str, Any]:
    """Check the health and configuration of the self-healing subsystem."""
    settings = _scraper_service.settings
    collector_id = (
        settings.brightdata_collector_id
        if settings.scraper_mode.value == "brightdata"
        else settings.mock_collector_id
    )
    return {
        "status": "online",
        "module": "self-healing",
        "scraper_mode": settings.scraper_mode.value,
        "collector_id": collector_id,
        "unlocker_zone": settings.brightdata_unlocker_zone,
        "confidence_threshold": settings.healing_confidence_threshold,
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
    Self-Healing Demonstration Endpoint (Single Mutation).

    Executes unified self-healing engine on single price mutation.
    """
    logger.info("Executing controlled single-selector self-healing sequence")
    _scraper_service.execute_dict(trigger_failure=False)

    initial_selectors = {
        "title": ".product-title",
        "price": ".product-price",
        "stock_status": ".product-status",
    }

    healing_result: HealingResult = _healing_manager.heal_html(
        html_content=DEMO_MUTATED_HTML,
        initial_selectors=initial_selectors,
    )

    return _build_unified_payload(healing_result, initial_selectors)


@router.post("/multi-demo")
@router.get("/multi-demo")
def run_multi_healing_demo() -> dict[str, Any]:
    """
    Multi-selector self-healing demo endpoint.
    Mutates title, price, and stock status across the full catalog, repairs all rules, and recovers dataset.
    """
    logger.info("Executing multi-selector self-healing sequence across full catalog")
    _scraper_service.execute_dict(trigger_failure=False)

    initial_selectors = {
        "title": ".product-title",
        "price": ".product-price",
        "stock_status": ".product-status",
    }

    mutated_html = get_mutated_catalog_html()

    healing_result: HealingResult = _healing_manager.heal_html(
        html_content=mutated_html,
        initial_selectors=initial_selectors,
    )

    return _build_unified_payload(healing_result, initial_selectors)


@router.post("/recover")
@router.get("/recover")
def run_unified_recovery(
    url: str | None = Query(default=None),
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """
    Unified Self-Healing Recovery Endpoint.

    Detects and repairs broken selectors and recovers dataset for either live URLs or mock sites.
    """
    target_url = url or (payload.get("url") if payload else None) or _scraper_service.settings.target_url

    initial_selectors = {
        "title": ".product-title",
        "price": ".product-price",
        "stock_status": ".product-status",
    }

    # If live brightdata mode and valid HTTP URL, run live self-healing pipeline
    if _scraper_service.settings.scraper_mode.value == "brightdata" and target_url and str(target_url).startswith("http"):
        logger.info("Executing live self-healing recovery pipeline on target URL: %s", target_url)
        healing_result = _healing_manager.heal_live(
            target_url=str(target_url),
            initial_selectors=initial_selectors,
        )
        return _build_unified_payload(healing_result, initial_selectors)

    return run_multi_healing_demo()
