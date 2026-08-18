"""Normalize raw scraper records into consistent product fields."""

import logging
import re
from typing import Any

from backend.scraper.models import ProductRecord

logger = logging.getLogger(__name__)

_PRICE_PATTERN = re.compile(r"[\d,.]+")
_STOCK_IN_STOCK = {"in stock", "available", "yes", "true", "instock"}
_STOCK_OUT_OF_STOCK = {"out of stock", "unavailable", "no", "false", "sold out", "outofstock"}


def normalize_price(raw_price: Any) -> str:
    """Normalize price to a USD-style string, e.g. '$49.99'."""
    if raw_price is None:
        return ""

    text = str(raw_price).strip()
    if not text:
        return ""

    if text.startswith("$"):
        return text

    match = _PRICE_PATTERN.search(text.replace(",", ""))
    if not match:
        logger.warning("Could not parse price from value: %r", raw_price)
        return text

    try:
        amount = float(match.group())
    except ValueError:
        return text

    return f"${amount:.2f}"


def normalize_title(raw_title: Any) -> str:
    """Strip and collapse whitespace in product titles."""
    if raw_title is None:
        return ""
    return " ".join(str(raw_title).split())


def normalize_stock_status(raw_status: Any) -> str:
    """Map varied stock labels to 'In Stock' or 'Out of Stock'."""
    if raw_status is None:
        return ""

    normalized = str(raw_status).strip().lower()
    if not normalized:
        return ""

    if normalized in _STOCK_IN_STOCK:
        return "In Stock"
    if normalized in _STOCK_OUT_OF_STOCK:
        return "Out of Stock"

    if "in stock" in normalized:
        return "In Stock"
    if "out" in normalized and "stock" in normalized:
        return "Out of Stock"

    return str(raw_status).strip()


def normalize_record(raw_record: dict[str, Any]) -> ProductRecord:
    """Normalize a single raw product dictionary."""
    return ProductRecord(
        title=normalize_title(raw_record.get("title")),
        price=normalize_price(raw_record.get("price")),
        stock_status=normalize_stock_status(
            raw_record.get("stock_status", raw_record.get("status"))
        ),
    )


def normalize_records(raw_records: list[dict[str, Any]]) -> list[ProductRecord]:
    """Normalize a list of raw product dictionaries."""
    logger.debug("Normalizing %d raw record(s)", len(raw_records))
    return [normalize_record(record) for record in raw_records]
