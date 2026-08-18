"""Tests for the modular scraping layer."""

from typing import Any

import pytest

from backend.scraper.exceptions import ScraperExecutionError, ScraperValidationError
from backend.scraper.models import RawScrapePayload, ScrapeStatus
from backend.scraper.normalizer import normalize_record, normalize_records
from backend.scraper.service import ScraperService
from backend.scraper.validator import validate_record, validate_records


class FakeScraperClient:
    """Test double for ScraperClient."""

    def __init__(self, payload: RawScrapePayload | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, bool]] = []

    def execute(self, *, trigger_failure: bool = False) -> RawScrapePayload:
        self.calls.append({"trigger_failure": trigger_failure})
        if self.error:
            raise self.error
        assert self.payload is not None
        return self.payload


def test_successful_response():
    client = FakeScraperClient(
        payload=RawScrapePayload(
            collector_id="c_test_001",
            records=[
                {
                    "title": "  Wireless Gaming Mouse  ",
                    "price": "49.99",
                    "stock_status": "available",
                }
            ],
        )
    )
    service = ScraperService(client=client)

    result = service.execute()

    assert result.status == ScrapeStatus.SUCCESS
    assert result.collector_id == "c_test_001"
    assert result.records_extracted == 1
    assert result.data[0].title == "Wireless Gaming Mouse"
    assert result.data[0].price == "$49.99"
    assert result.data[0].stock_status == "In Stock"
    assert result.error is None


def test_empty_response():
    client = FakeScraperClient(
        payload=RawScrapePayload(
            collector_id="c_test_002",
            records=[],
        )
    )
    service = ScraperService(client=client)

    result = service.execute()

    assert result.status == ScrapeStatus.FAILED
    assert result.records_extracted == 0
    assert result.data == []
    assert result.error == "Scrape returned no records"


def test_invalid_response_missing_required_fields():
    client = FakeScraperClient(
        payload=RawScrapePayload(
            collector_id="c_test_003",
            records=[{"title": "Mouse", "price": "", "stock_status": "In Stock"}],
        )
    )
    service = ScraperService(client=client)

    result = service.execute()

    assert result.status == ScrapeStatus.FAILED
    assert result.records_extracted == 0
    assert "Validation failed" in (result.error or "")
    assert "price is required" in (result.error or "")


def test_api_failure():
    client = FakeScraperClient(
        error=ScraperExecutionError("Bright Data API request failed: timeout")
    )
    service = ScraperService(client=client)

    result = service.execute()

    assert result.status == ScrapeStatus.FAILED
    assert result.records_extracted == 0
    assert "Bright Data API request failed" in (result.error or "")


def test_client_execution_error_from_payload():
    client = FakeScraperClient(
        payload=RawScrapePayload(
            collector_id="c_test_004",
            records=[],
            error="SelectorNotFound: .product-price",
        )
    )
    service = ScraperService(client=client)

    result = service.execute(trigger_failure=True)

    assert result.status == ScrapeStatus.FAILED
    assert result.error == "SelectorNotFound: .product-price"
    assert client.calls == [{"trigger_failure": True}]


def test_normalizer_maps_status_field():
    normalized = normalize_record(
        {"title": "Keyboard", "price": "$79.00", "status": "out of stock"}
    )
    assert normalized.stock_status == "Out of Stock"


def test_validator_raises_on_empty_list():
    with pytest.raises(ScraperValidationError) as exc_info:
        validate_records([])
    assert "records is empty" in exc_info.value.field_errors


def test_validator_raises_on_missing_title():
    with pytest.raises(ScraperValidationError):
        validate_record(
            normalize_record({"title": "", "price": "$10.00", "stock_status": "In Stock"}),
            record_index=0,
        )


def test_normalize_records_returns_product_models():
    records = normalize_records(
        [{"title": "Monitor", "price": "199", "stock_status": "In Stock"}]
    )
    assert len(records) == 1
    assert records[0].price == "$199.00"


def test_execute_dict_is_json_serializable():
    client = FakeScraperClient(
        payload=RawScrapePayload(
            collector_id="c_test_005",
            records=[{"title": "Desk", "price": "$120.00", "stock_status": "In Stock"}],
        )
    )
    service = ScraperService(client=client)

    payload: dict[str, Any] = service.execute_dict()

    assert payload["status"] == "success"
    assert payload["data"][0]["title"] == "Desk"
