"""Failure detection engine for the ScrapeVerse self-healing system."""

import logging
import re
from typing import Any

from backend.automation.models import FailureType, ScrapeFailure
from backend.scraper.models import ProductRecord, ScrapeResult, ScrapeStatus

logger = logging.getLogger(__name__)

# Common regex patterns to identify failed field and broken selector
_SELECTOR_ERROR_RE = re.compile(
    r"(?:SelectorNotFound|NoSuchElement|MissingSelector):\s*([.\#\[\]\w\-_]+)",
    re.IGNORECASE,
)
_FIELD_HINT_PATTERNS: dict[str, list[re.Pattern]] = {
    "price": [re.compile(r"price", re.I), re.compile(r"cost", re.I), re.compile(r"amount", re.I)],
    "title": [re.compile(r"title", re.I), re.compile(r"name", re.I), re.compile(r"heading", re.I)],
    "stock_status": [
        re.compile(r"stock", re.I),
        re.compile(r"availab", re.I),
        re.compile(r"status", re.I),
    ],
}


class FailureDetector:
    """
    Analyzes scraper results and detects failures.

    Detects:
    - Scraper status='failed'
    - Selector-not-found errors (e.g. 'SelectorNotFound: .product-price')
    - Empty data responses (records_extracted=0 or empty list)
    - Missing required fields (e.g. empty title, price, or stock status)
    - Invalid extracted values
    - API and runtime execution errors
    """

    def __init__(self, required_fields: tuple[str, ...] = ("title", "price", "stock_status")) -> None:
        self.required_fields = required_fields

    def detect(self, result: ScrapeResult | dict[str, Any] | None) -> ScrapeFailure | None:
        """
        Evaluate a scrape result.

        Returns a structured ScrapeFailure if an issue is detected, or None if valid.
        """
        if result is None:
            return ScrapeFailure(
                scraper_id="unknown",
                failure_type=FailureType.EMPTY_RESPONSE.value,
                error="Scraper returned null/empty result",
            )

        # Normalize input to ScrapeResult or standard dict fields
        if isinstance(result, ScrapeResult):
            scraper_id = result.collector_id
            status = result.status
            records_count = result.records_extracted
            data = result.data
            error = result.error
        elif isinstance(result, dict):
            scraper_id = str(result.get("collector_id", "unknown"))
            status = result.get("status", ScrapeStatus.SUCCESS.value)
            records_count = result.get("records_extracted", len(result.get("data", [])))
            data = result.get("data", [])
            error = result.get("error")
        else:
            return ScrapeFailure(
                scraper_id="unknown",
                failure_type=FailureType.INVALID_VALUE.value,
                error=f"Unrecognized scrape result type: {type(result)}",
            )

        # 1. Check for missing required fields or invalid values in extracted records if data present
        if data:
            for idx, record in enumerate(data):
                rec_dict = record.model_dump() if isinstance(record, ProductRecord) else dict(record)
                for field in self.required_fields:
                    val = rec_dict.get(field)
                    if val is None or not str(val).strip():
                        logger.warning("Failure detected: Missing required field '%s' in record %d", field, idx)
                        return ScrapeFailure(
                            scraper_id=scraper_id,
                            failure_type=FailureType.VALIDATION_ERROR.value,
                            field=field,
                            old_selector=f".product-{field.replace('_', '-')}",
                            error=f"Required field '{field}' is missing or empty in record {idx}",
                        )

                    # Invalid value checks (e.g. price has no digits)
                    if field == "price" and not any(ch.isdigit() for ch in str(val)):
                        logger.warning("Failure detected: Invalid price value '%s' in record %d", val, idx)
                        return ScrapeFailure(
                            scraper_id=scraper_id,
                            failure_type=FailureType.INVALID_VALUE.value,
                            field="price",
                            old_selector=".product-price",
                            error=f"Invalid price value '{val}' (contains no numeric digits)",
                        )

        # 2. Check for explicit error message or failed status
        if status == ScrapeStatus.FAILED.value or status == ScrapeStatus.FAILED or error:
            error_str = error or "Scrape operation returned failed status"
            return self._classify_error(scraper_id, error_str)

        # 3. Check for empty records payload
        if records_count == 0 or not data:
            logger.warning("Failure detected: Scraper returned 0 records")
            return ScrapeFailure(
                scraper_id=scraper_id,
                failure_type=FailureType.EMPTY_RESPONSE.value,
                error="Scraper returned 0 extracted records",
            )

        # Scrape succeeded with valid data
        return None


    def detect_all(self, result: ScrapeResult | dict[str, Any] | None) -> list[ScrapeFailure]:
        """
        Scan a scrape result and return ALL distinct field failures.

        Used for batch analysis to repair multiple broken fields in one analysis pass.
        Deduplicates by field so multi-record failures produce one repair per broken selector rule.
        """
        first = self.detect(result)
        if not first:
            return []

        data = (
            result.data
            if isinstance(result, ScrapeResult)
            else (result.get("data", []) if isinstance(result, dict) else [])
        )
        scraper_id = (
            result.collector_id
            if isinstance(result, ScrapeResult)
            else (str(result.get("collector_id", "unknown")) if isinstance(result, dict) else "unknown")
        )

        # If data payload is empty or zero records extracted, all required fields are failing
        if not data:
            return [
                ScrapeFailure(
                    scraper_id=scraper_id,
                    failure_type=first.failure_type,
                    field=field,
                    old_selector=f".product-{field.replace('_', '-')}",
                    error=f"Required field '{field}' could not be extracted (0 records)",
                )
                for field in self.required_fields
            ]

        failures_by_field: dict[str, ScrapeFailure] = {}
        for idx, record in enumerate(data):
            rec_dict = record.model_dump() if isinstance(record, ProductRecord) else dict(record)
            for field in self.required_fields:
                if field in failures_by_field:
                    continue
                val = rec_dict.get(field)
                if val is None or not str(val).strip():
                    failures_by_field[field] = ScrapeFailure(
                        scraper_id=scraper_id,
                        failure_type=FailureType.VALIDATION_ERROR.value,
                        field=field,
                        old_selector=f".product-{field.replace('_', '-')}",
                        error=f"Required field '{field}' is missing or empty in record {idx}",
                    )
                elif field == "price" and not any(ch.isdigit() for ch in str(val)):
                    failures_by_field[field] = ScrapeFailure(
                        scraper_id=scraper_id,
                        failure_type=FailureType.INVALID_VALUE.value,
                        field="price",
                        old_selector=".product-price",
                        error=f"Invalid price value '{val}' (no numeric digits)",
                    )

        if failures_by_field:
            return list(failures_by_field.values())

        return [first]


    def _classify_error(self, scraper_id: str, error_str: str) -> ScrapeFailure:
        """Classify error string into a specific failure category, field, and selector."""
        # Check for selector not found
        match = _SELECTOR_ERROR_RE.search(error_str)
        if match:
            old_selector = match.group(1).strip()
            inferred_field = self._infer_field(old_selector) or self._infer_field(error_str)
            return ScrapeFailure(
                scraper_id=scraper_id,
                failure_type=FailureType.SELECTOR_NOT_FOUND.value,
                field=inferred_field,
                old_selector=old_selector,
                error=error_str,
            )

        if "selector" in error_str.lower():
            inferred_field = self._infer_field(error_str)
            return ScrapeFailure(
                scraper_id=scraper_id,
                failure_type=FailureType.SELECTOR_NOT_FOUND.value,
                field=inferred_field,
                old_selector=None,
                error=error_str,
            )

        if "validation" in error_str.lower() or "required" in error_str.lower():
            inferred_field = self._infer_field(error_str)
            return ScrapeFailure(
                scraper_id=scraper_id,
                failure_type=FailureType.VALIDATION_ERROR.value,
                field=inferred_field,
                old_selector=None,
                error=error_str,
            )

        if "empty" in error_str.lower() or "no records" in error_str.lower():
            return ScrapeFailure(
                scraper_id=scraper_id,
                failure_type=FailureType.EMPTY_RESPONSE.value,
                error=error_str,
            )

        return ScrapeFailure(
            scraper_id=scraper_id,
            failure_type=FailureType.API_ERROR.value,
            field=self._infer_field(error_str),
            error=error_str,
        )

    def _infer_field(self, text: str) -> str | None:
        """Infer which product attribute failed based on selector or error text."""
        for field, patterns in _FIELD_HINT_PATTERNS.items():
            for pat in patterns:
                if pat.search(text):
                    return field
        return None
