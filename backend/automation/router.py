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
def run_healing_test() -> dict[str, Any]:
    """
    Demonstrate the self-healing workflow.

    Simulates a scraper failure (broken selector), runs DOM analysis,
    proposes a selector repair, retries scraping, and validates recovery.
    """
    logger.info("Executing self-healing demonstration test")

    # Step 1: Simulate a failed scrape run
    failed_initial_result = _scraper_service.execute_dict(trigger_failure=True)

    # Step 2: Trigger self-healing
    healing_result: HealingResult = _healing_manager.heal(
        initial_result=failed_initial_result,
        scrape_fn=_scraper_service.execute_dict,
    )

    first_event = healing_result.attempts[0] if healing_result.attempts else None
    first_repair = healing_result.selector_repairs[0] if healing_result.selector_repairs else None

    return {
        "status": healing_result.status,
        "repaired": healing_result.repaired,
        "failure_type": first_event.failure_type if first_event else "Unknown",
        "old_selector": first_repair.old_selector if first_repair else None,
        "new_selector": first_repair.new_selector if first_repair else None,
        "confidence": first_repair.confidence if first_repair else None,
        "validation_result": first_event.validation_result if first_event else None,
        "retry_count": first_event.retry_count if first_event else 0,
        "healing_event": first_event.to_dict() if first_event else None,
        "healing_result": healing_result.to_dict(),
    }
