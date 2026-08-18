"""
ScrapeVerse scraping module — public exports for Person 2 and FastAPI routes.

Usage:
    from backend.scraper import ScraperService, run_scrape

    result = run_scrape()
    # or
    service = ScraperService()
    payload = service.execute_dict()
"""

from backend.scraper.exceptions import (
    ScraperError,
    ScraperExecutionError,
    ScraperValidationError,
)
from backend.scraper.models import ProductRecord, ScrapeResult, ScrapeStatus
from backend.scraper.service import ScraperService, create_scraper_client, run_scrape

__all__ = [
    "ProductRecord",
    "ScrapeResult",
    "ScrapeStatus",
    "ScraperError",
    "ScraperExecutionError",
    "ScraperService",
    "ScraperValidationError",
    "create_scraper_client",
    "run_scrape",
]
