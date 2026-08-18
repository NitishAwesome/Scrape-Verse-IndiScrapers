from fastapi import FastAPI
from backend.scraper.mock_scraper import run_scraper

app = FastAPI(title="ScrapeVerse Backend Engine")

@app.get("/")
def root():
    return {"status": "online", "message": "ScrapeVerse Engine Active"}

@app.get("/api/scrape")
def execute_scrape(fail: bool = False):
    return run_scraper(trigger_failure=fail)