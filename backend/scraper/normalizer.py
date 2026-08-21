"""Normalize raw scraper records into consistent product fields."""

import logging
import re
from typing import Any

from backend.scraper.models import ProductRecord

logger = logging.getLogger(__name__)

_PRICE_PATTERN = re.compile(r"[\d,.]+")
_STOCK_IN_STOCK = {"in stock", "available", "yes", "true", "instock"}
_STOCK_OUT_OF_STOCK = {"out of stock", "unavailable", "no", "false", "sold out", "outofstock"}


_WORD_TO_RATING = {
    "zero": 0.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
}


def normalize_price(raw_price: Any) -> str:
    """Normalize price to a USD-style string, e.g. '$49.99' or handle dicts {'value': 45.17}."""
    if raw_price is None:
        return ""

    if isinstance(raw_price, dict):
        val = raw_price.get("value")
        if val is not None:
            try:
                return f"${float(val):.2f}"
            except ValueError:
                return str(val)
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

    if "in stock" in normalized or "instock" in normalized:
        return "In Stock"
    if "out" in normalized and "stock" in normalized:
        return "Out of Stock"

    return str(raw_status).strip()


def normalize_rating(raw_rating: Any) -> float | None:
    """Normalize rating to a float (e.g. 4.8 from '★ 4.8' or 'Four' -> 4.0)."""
    if raw_rating is None:
        return None
    
    if isinstance(raw_rating, (int, float)):
        return float(raw_rating)

    text = str(raw_rating).replace("★", "").strip().lower()
    if text in _WORD_TO_RATING:
        return _WORD_TO_RATING[text]

    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def normalize_category(raw_category: Any) -> str | None:
    """Normalize category name."""
    if not raw_category:
        return None
    return str(raw_category).strip().title()


def normalize_record(raw_record: dict[str, Any]) -> ProductRecord:
    """Normalize a single raw product dictionary."""
    rating_val = raw_record.get("rating")
    if rating_val is None:
        rating_val = raw_record.get("product_rating")

    category_val = raw_record.get("category")
    if category_val is None:
        category_val = raw_record.get("product_category") or raw_record.get("category_name")

    url_val = (
        raw_record.get("product_url")
        or raw_record.get("book_url")
        or raw_record.get("url")
        or raw_record.get("link")
    )
    prod_id_val = raw_record.get("product_id") or raw_record.get("id") or raw_record.get("sku")

    return ProductRecord(
        title=normalize_title(raw_record.get("title") or raw_record.get("name")),
        price=normalize_price(raw_record.get("price")),
        stock_status=normalize_stock_status(
            raw_record.get("stock_status") or raw_record.get("status") or raw_record.get("availability")
        ),
        rating=normalize_rating(rating_val),
        category=normalize_category(category_val),
        product_url=str(url_val).strip() if url_val else None,
        product_id=str(prod_id_val).strip() if prod_id_val else None,
    )


def normalize_records(raw_records: list[dict[str, Any]]) -> list[ProductRecord]:
    """Normalize a list of raw product dictionaries."""
    logger.debug("Normalizing %d raw record(s)", len(raw_records))
    return [normalize_record(record) for record in raw_records]
