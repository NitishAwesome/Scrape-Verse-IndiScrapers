"""
ScrapeVerse Automation & Self-Healing Module.

Exposes data contracts and healing interfaces.
"""

from backend.automation.models import (
    FailureType,
    HealingEvent,
    HealingResult,
    HealingStatus,
    ScrapeFailure,
    SelectorRepair,
)

__all__ = [
    "FailureType",
    "HealingEvent",
    "HealingResult",
    "HealingStatus",
    "ScrapeFailure",
    "SelectorRepair",
]
