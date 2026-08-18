"""Scraper-specific exceptions."""


class ScraperError(Exception):
    """Base error for the scraping module."""


class ScraperExecutionError(ScraperError):
    """Raised when scraper execution fails (network, selector, API error)."""


class ScraperValidationError(ScraperError):
    """Raised when normalized data is missing required fields."""

    def __init__(self, message: str, *, field_errors: list[str] | None = None):
        super().__init__(message)
        self.field_errors = field_errors or []
