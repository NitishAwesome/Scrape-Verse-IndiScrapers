"""Pydantic models for the scraping pipeline."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScrapeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class ProductRecord(BaseModel):
    """Normalized product fields consumed by automation and dashboard."""

    title: str
    price: str
    stock_status: str = Field(description="Normalized stock label, e.g. 'In Stock'")


class ScrapeResult(BaseModel):
    """Stable response contract for Person 2 (automation) and Person 3 (dashboard)."""

    collector_id: str
    status: ScrapeStatus
    records_extracted: int
    data: list[ProductRecord] = Field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RawScrapePayload(BaseModel):
    """Shape returned by scraper clients before normalization."""

    collector_id: str
    records: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
