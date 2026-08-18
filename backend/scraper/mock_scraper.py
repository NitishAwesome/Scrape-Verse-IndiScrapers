"""
Backward-compatible wrapper for the original mock_scraper module.

Prefer importing from backend.scraper.service for new code.
"""

from backend.scraper.service import ScraperService

_service = ScraperService()


def run_scrape(fail: bool = False, trigger_failure: bool = False) -> dict:
    """Run scrape and return dict result, supporting fail/trigger_failure flags."""
    return _service.execute_dict(trigger_failure=(fail or trigger_failure))


def run_scraper(trigger_failure: bool = False, fail: bool = False) -> dict:
    """Legacy helper used before the service layer existed."""
    return run_scrape(fail=fail, trigger_failure=trigger_failure)

