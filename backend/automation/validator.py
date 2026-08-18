"""Validation logic for confirming successful scraper self-healing."""

import logging
from typing import Any

from backend.scraper.models import ProductRecord, ScrapeResult, ScrapeStatus

logger = logging.getLogger(__name__)


class HealingValidator:
    """
    Validates whether a post-repair scrape run successfully resolved the failure.

    Checks:
    - Status is 'success'
    - At least 1 record extracted
    - Required fields (title, price, stock_status) are populated and valid
    - Specifically validates the repaired target field
    """

    def __init__(self, required_fields: tuple[str, ...] = ("title", "price", "stock_status")) -> None:
        self.required_fields = required_fields

    def validate(
        self,
        result: ScrapeResult | dict[str, Any] | None,
        target_field: str | None = None,
    ) -> tuple[bool, str]:
        """
        Validate a scrape result after a healing attempt.

        Returns (is_valid: bool, reason: str).
        """
        if result is None:
            return False, "Validation failed: Scrape result is None"

        if isinstance(result, ScrapeResult):
            status = result.status
            records_count = result.records_extracted
            data = result.data
            error = result.error
        elif isinstance(result, dict):
            status = result.get("status", ScrapeStatus.SUCCESS.value)
            records_count = result.get("records_extracted", len(result.get("data", [])))
            data = result.get("data", [])
            error = result.get("error")
        else:
            return False, f"Validation failed: Unexpected result type {type(result)}"

        if status == ScrapeStatus.FAILED.value or status == ScrapeStatus.FAILED:
            return False, f"Validation failed: Scraper returned status='failed' ({error or 'No error message'})"

        if error:
            return False, f"Validation failed: Scraper reported error: {error}"

        if records_count == 0 or not data:
            return False, "Validation failed: Extracted record set is empty"

        # Check required fields in all extracted records
        for idx, record in enumerate(data):
            rec_dict = record.model_dump() if isinstance(record, ProductRecord) else dict(record)
            for field in self.required_fields:
                val = rec_dict.get(field)
                if val is None or not str(val).strip():
                    return False, f"Validation failed: Field '{field}' is missing in record {idx}"

                if field == "price" and not any(ch.isdigit() for ch in str(val)):
                    return False, f"Validation failed: Price '{val}' has no numeric digits in record {idx}"

        if target_field:
            logger.info("Successfully validated repaired field '%s'", target_field)
            return True, f"Validation successful: Extracted {records_count} record(s) with valid '{target_field}'"

        logger.info("Validation successful for %d extracted record(s)", records_count)
        return True, f"Validation successful: Extracted {records_count} valid record(s)"
