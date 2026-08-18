"""
ScrapeVerse Automation & Self-Healing Module.

Exposes data models and engines for failure detection, DOM analysis,
selector repair, and healing management.
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
]
