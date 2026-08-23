"""Pydantic models for the automation and self-healing subsystem."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FailureType(str, Enum):
    """Common categories of scraping failures."""

    SELECTOR_NOT_FOUND = "SelectorNotFound"
    FIELD_MISSING = "FieldMissing"
    EMPTY_RESPONSE = "EmptyResponse"
    VALIDATION_ERROR = "ValidationError"
    INVALID_VALUE = "InvalidValue"
    DOM_CHANGED = "DOMChanged"
    LOW_CONFIDENCE = "LowConfidence"
    UNSUPPORTED_STRUCTURE = "UnsupportedStructure"
    API_ERROR = "ApiError"
    UNKNOWN = "Unknown"


class Recoverability(str, Enum):
    """Assessment of whether a scraping failure can be safely repaired from DOM evidence."""

    RECOVERABLE = "recoverable"
    PARTIALLY_RECOVERABLE = "partially_recoverable"
    AMBIGUOUS_UNSAFE = "ambiguous_unsafe"
    UNSUPPORTED = "unsupported"


class FailureClassification(BaseModel):
    """Structured diagnosis of an extraction failure and its recoverability."""

    failure_type: str = Field(
        default=FailureType.DOM_CHANGED.value,
        description="Classified category of scraping failure",
    )
    affected_fields: list[str] = Field(
        default_factory=list,
        description="Fields identified as broken or missing in the dataset",
    )
    recoverability: str = Field(
        default=Recoverability.RECOVERABLE.value,
        description="Recoverability tier: recoverable, partially_recoverable, ambiguous_unsafe, unsupported",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Diagnostic confidence in DOM analysis assessment",
    )
    reason: str = Field(
        description="Evidence-based reasoning explaining why failure occurred and recoverability state",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class HealingStatus(str, Enum):
    """Status outcomes for a healing attempt or overall healing process."""

    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class DOMCandidate(BaseModel):
    """Represents a candidate HTML element identified during DOM analysis."""

    tag: str = Field(description="HTML tag name, e.g. 'p', 'span', 'h2'")
    classes: list[str] = Field(default_factory=list, description="CSS classes on element")
    element_id: str | None = Field(default=None, description="id attribute if present")
    attributes: dict[str, str] = Field(default_factory=dict, description="HTML element attributes")
    text: str = Field(default="", description="Inner text content of element")
    suggested_selector: str = Field(description="Calculated CSS selector targeting this candidate")
    field_hint: str | None = Field(default=None, description="Inferred target field (e.g. 'price')")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reasoning: str | None = Field(default=None, description="Explanation for candidate match")

    @property
    def reason(self) -> str | None:
        return self.reasoning

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ScrapeFailure(BaseModel):
    """
    Represents a detected scraping failure.

    Captured when a scrape run returns status='failed' or encounters an error.
    """

    scraper_id: str
    failure_type: str = Field(
        default=FailureType.SELECTOR_NOT_FOUND.value,
        description="Category of failure (e.g. SelectorNotFound, ValidationError)",
    )
    field: str | None = Field(
        default=None,
        description="The specific product field that failed (e.g. 'price', 'title')",
    )
    old_selector: str | None = Field(
        default=None,
        description="The CSS selector that failed or became obsolete",
    )
    error: str = Field(description="Raw error message from the scraper")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when failure was detected",
    )

    @property
    def target_field(self) -> str | None:
        return self.field

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DataQualityMetrics(BaseModel):
    """Quality metrics calculated from recovered extraction dataset."""

    total_records: int = Field(default=0, description="Total count of records returned")
    valid_records: int = Field(default=0, description="Count of records passing contract validation")
    invalid_records: int = Field(default=0, description="Count of records with missing/invalid fields")
    title_completeness: float = Field(default=100.0, description="Percentage of records with valid title")
    price_completeness: float = Field(default=100.0, description="Percentage of records with valid numeric price")
    stock_completeness: float = Field(default=100.0, description="Percentage of records with valid stock status")
    overall_quality_score: float = Field(default=100.0, description="Overall average field completeness percentage")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SelectorRepair(BaseModel):
    """
    Represents an AI or rule-based proposed selector repair.

    Generated after analyzing the updated DOM / HTML structure.
    """

    field: str = Field(description="Target field being repaired, e.g. 'price'")
    old_selector: str = Field(description="Broken/obsolete selector")
    new_selector: str = Field(description="Repaired selector identified from DOM")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    reasoning: str | None = Field(
        default=None,
        description="Explanation for why this new selector was chosen",
    )
    candidates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Ranked candidate selectors evaluated for this field",
    )

    @property
    def target_field(self) -> str:
        return self.field

    @property
    def reason(self) -> str | None:
        return self.reasoning

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class HealingEvent(BaseModel):
    """
    Represents one complete healing attempt cycle.

    Tracks selector replacement, retry execution, and outcome.
    """

    scraper_id: str
    failure_type: str = Field(default=FailureType.SELECTOR_NOT_FOUND.value)
    old_selector: str | None = None
    new_selector: str | None = None
    target_field: str | None = None
    confidence: float | None = None
    validation_result: bool | str | None = Field(
        default=None,
        description="Result of post-repair validation check",
    )
    retry_count: int = Field(default=1, description="Iteration/attempt number")
    status: str = Field(
        default=HealingStatus.SUCCESS.value,
        description="Outcome of this attempt ('success', 'failed', 'in_progress')",
    )
    message: str | None = Field(default=None, description="Status/diagnostic message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the healing attempt",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class HealingResult(BaseModel):
    """
    Represents the final result of the self-healing process.

    Returned to caller/API and consumed by the dashboard to show healing logs.
    """

    status: str = Field(
        default=HealingStatus.SUCCESS.value,
        description="Final status of healing ('success' or 'failed')",
    )
    repaired: bool = Field(
        default=False,
        description="True if scraper was successfully healed and validated",
    )
    attempts: list[HealingEvent] = Field(
        default_factory=list,
        description="List of healing attempts made during this session",
    )
    selector_repairs: list[SelectorRepair] = Field(
        default_factory=list,
        description="All selector repairs applied during healing",
    )
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted and normalized product dataset recovered by self-healing",
    )
    error: str | None = Field(
        default=None,
        description="Error details if self-healing could not resolve the issue",
    )
    records_before: int = Field(
        default=0,
        description="Count of valid records before healing attempt",
    )
    records_after: int = Field(
        default=0,
        description="Count of valid records extracted after healing",
    )
    fields_detected_as_broken: list[str] = Field(
        default_factory=list,
        description="Names of fields detected as missing/invalid in baseline",
    )
    fields_repaired: list[str] = Field(
        default_factory=list,
        description="Names of fields successfully repaired and validated",
    )
    overall_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence score across all repaired fields",
    )
    duration_ms: float = Field(
        default=0.0,
        description="Total duration of the recovery cycle in milliseconds",
    )
    verified: bool = Field(
        default=False,
        description="True if post-repair extraction passed contract validation with non-empty data",
    )
    data_quality: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed quality metrics for the recovered dataset",
    )
    failure_classification: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured failure diagnosis and recoverability state",
    )
    recovery_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured before -> healing -> after audit comparison",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
