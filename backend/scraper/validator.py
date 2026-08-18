"""Validate normalized product records."""

import logging

from backend.scraper.exceptions import ScraperValidationError
from backend.scraper.models import ProductRecord

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("title", "price", "stock_status")


def validate_record(record: ProductRecord, *, record_index: int = 0) -> None:
    """Ensure a normalized record contains all required fields."""
    errors: list[str] = []

    if not record.title.strip():
        errors.append(f"record[{record_index}].title is required")
    if not record.price.strip():
        errors.append(f"record[{record_index}].price is required")
    if not record.stock_status.strip():
        errors.append(f"record[{record_index}].stock_status is required")

    if errors:
        logger.warning("Validation failed for record %d: %s", record_index, errors)
        raise ScraperValidationError(
            "Normalized record is missing required fields",
            field_errors=errors,
        )


def validate_records(records: list[ProductRecord]) -> None:
    """Validate a list of normalized records."""
    if not records:
        raise ScraperValidationError(
            "Scrape returned no records to validate",
            field_errors=["records is empty"],
        )

    for index, record in enumerate(records):
        validate_record(record, record_index=index)
