import logging

from fastapi import FastAPI

from backend.automation.router import router as healing_router
from backend.scraper.service import ScraperService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="ScrapeGuard Backend Engine")
app.include_router(healing_router)

scraper_service = ScraperService()


@app.get("/")
def root():
    return {"status": "online", "message": "ScrapeGuard Engine Active"}


@app.get("/api/scrape")
def execute_scrape(fail: bool = False, url: str | None = None):
    return scraper_service.execute_dict(target_url=url, trigger_failure=fail)
