import logging

from fastapi import FastAPI

from backend.automation.router import router as healing_router
from backend.scraper.service import ScraperService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="ScrapeVerse Backend Engine")
app.include_router(healing_router)

scraper_service = ScraperService()


@app.get("/")
def root():
    return {"status": "online", "message": "ScrapeVerse Engine Active"}


@app.get("/api/scrape")
def execute_scrape(fail: bool = False):
    return scraper_service.execute_dict(trigger_failure=fail)
