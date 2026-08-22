"""Environment-based configuration for the scraping module."""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperMode(str, Enum):
    MOCK = "mock"
    BRIGHTDATA = "brightdata"


class ScraperSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    scraper_mode: ScraperMode = Field(default=ScraperMode.MOCK, alias="SCRAPER_MODE")
    mock_collector_id: str = Field(default="c_mock_123456", alias="MOCK_COLLECTOR_ID")
    mock_site_path: Path = Field(
        default=Path("mock-site/index.html"),
        alias="MOCK_SITE_PATH",
    )

    brightdata_api_token: str | None = Field(default=None, alias="BRIGHTDATA_API_TOKEN")
    brightdata_collector_id: str | None = Field(
        default="c_mt3d61eq4viqmv3f4", alias="BRIGHTDATA_COLLECTOR_ID"
    )
    brightdata_api_base_url: str = Field(
        default="https://api.brightdata.com", alias="BRIGHTDATA_API_BASE_URL"
    )
    brightdata_timeout_seconds: float = Field(
        default=60.0, alias="BRIGHTDATA_TIMEOUT_SECONDS"
    )
    target_url: str = Field(
        default="https://books.toscrape.com/catalogue/category/books/travel_2/index.html",
        alias="TARGET_URL",
    )
    brightdata_unlocker_zone: str = Field(
        default="unlocker", alias="BRIGHTDATA_UNLOCKER_ZONE"
    )
    healing_confidence_threshold: float = Field(
        default=0.75, alias="HEALING_CONFIDENCE_THRESHOLD"
    )
    max_healing_attempts: int = Field(
        default=10, alias="MAX_HEALING_ATTEMPTS"
    )


@lru_cache
def get_settings() -> ScraperSettings:
    return ScraperSettings()
