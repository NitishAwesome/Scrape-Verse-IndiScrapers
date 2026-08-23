"""
ScrapeGuard Automation & Self-Healing Module.

Exposes data models, engines, and FastAPI router for failure detection,
DOM analysis, selector repair, and healing management.
"""

from backend.automation.dom_analyzer import DOMAnalyzer
from backend.automation.failure_detector import FailureDetector
from backend.automation.healing_manager import HealingManager
from backend.automation.models import (
    DOMCandidate,
    FailureType,
    HealingEvent,
    HealingResult,
    HealingStatus,
    ScrapeFailure,
    SelectorRepair,
)
from backend.automation.router import router as healing_router
from backend.automation.selector_repair import SelectorRepairEngine
from backend.automation.validator import HealingValidator

__all__ = [
    "DOMAnalyzer",
    "DOMCandidate",
    "FailureDetector",
    "FailureType",
    "HealingEvent",
    "HealingManager",
    "HealingResult",
    "HealingStatus",
    "HealingValidator",
    "ScrapeFailure",
    "SelectorRepair",
    "SelectorRepairEngine",
    "healing_router",
]
