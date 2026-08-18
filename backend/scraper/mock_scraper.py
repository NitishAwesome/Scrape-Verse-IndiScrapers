"""
Backward-compatible wrapper for the original mock_scraper module.

Prefer importing from backend.scraper.service for new code.
"""

from backend.scraper.service import ScraperService

_service = ScraperService()


def run_scraper(trigger_failure: bool = False) -> dict:
    """Legacy helper used by backend/main.py before the service layer existed."""
    return _service.execute_dict(trigger_failure=trigger_failure)
