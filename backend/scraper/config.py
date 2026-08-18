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
    brightdata_collector_id: str | None = Field(default=None, alias="BRIGHTDATA_COLLECTOR_ID")
    brightdata_api_base_url: str = Field(
        default="https://api.brightdata.com",
        alias="BRIGHTDATA_API_BASE_URL",
    )
    brightdata_timeout_seconds: float = Field(default=30.0, alias="BRIGHTDATA_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> ScraperSettings:
    return ScraperSettings()
