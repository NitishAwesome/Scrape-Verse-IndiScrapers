"""DOM analysis engine for inspecting HTML and identifying candidate elements."""

import logging
import re
from html.parser import HTMLParser
from typing import Any

from backend.automation.models import DOMCandidate

logger = logging.getLogger(__name__)

_PRICE_VALUE_RE = re.compile(r"[\$€£¥₹]?\s*\d+(?:[.,]\d+)?")
_STOCK_TEXT_RE = re.compile(
    r"\b(in\s*stock|out\s*of\s*stock|available|unavailable|sold\s*out|instock|in-stock|left|only\s*\d+\s*left|\d+\s*left)\b",
    re.IGNORECASE,
)
_CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₹", "USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD"}


class _DOMElementParser(HTMLParser):
    """Parses HTML into a structured list of element representations."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []
        self._tag_stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v or "" for k, v in attrs}
        class_str = attr_dict.get("class", "")
        classes = [c.strip() for c in class_str.split() if c.strip()]
        element_id = attr_dict.get("id") or None

        parent = self._tag_stack[-1] if self._tag_stack else None

        elem = {
            "tag": tag.lower(),
            "classes": classes,
            "element_id": element_id,
            "attributes": attr_dict,
            "text_parts": [],
            "parent_tag": parent.get("tag") if parent else None,
            "parent_classes": parent.get("classes", []) if parent else [],
        }
        self.elements.append(elem)
        self._tag_stack.append(elem)

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and self._tag_stack:
            for item in self._tag_stack:
                item["text_parts"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack:
            self._tag_stack.pop()


class DOMAnalyzer:
    """
    Analyzes HTML content to find candidate DOM elements for failed fields.

    Finds candidate elements that represent missing fields (e.g. price, title, stock status)
    and computes suggested CSS selectors with confidence scores and reasoning.
    """

    def analyze(self, html_content: str, target_field: str | None = None) -> list[DOMCandidate]:
        """
        Analyze HTML and return candidate DOM elements.

        If target_field is provided ('price', 'title', 'stock_status'), candidates for that
        specific field are prioritized.
        """
        if not html_content or not html_content.strip():
            logger.warning("Empty HTML content provided to DOMAnalyzer")
            return []

        parser = _DOMElementParser()
        try:
            parser.feed(html_content)
        except Exception as exc:
            logger.error("Failed to parse HTML in DOMAnalyzer: %s", exc)
            return []

        candidates: list[DOMCandidate] = []
        seen_selectors: set[str] = set()

        for elem in parser.elements:
            text = " ".join(elem["text_parts"]).strip()
            tag = elem["tag"]
            classes = elem["classes"]
            element_id = elem["element_id"]
            attrs = elem["attributes"]

            # Also consider element title attribute if text is empty or truncated
            if attrs.get("title") and (not text or "..." in text):
                text = attrs["title"].strip()

            if not text and not classes and not element_id and not any(k.startswith("data-") for k in attrs):
                continue

            field_hint, confidence, reason = self._score_element(
                tag, classes, element_id, attrs, text, target_field, elem.get("parent_tag")
            )

            if field_hint and confidence > 0.0:
                selector = self._compute_selector(tag, classes, element_id, attrs, elem.get("parent_tag"))
                if selector not in seen_selectors:
                    seen_selectors.add(selector)
                    candidates.append(
                        DOMCandidate(
                            tag=tag,
                            classes=classes,
                            element_id=element_id,
                            attributes=attrs,
                            text=text,
                            suggested_selector=selector,
                            field_hint=field_hint,
                            confidence=confidence,
                            reasoning=reason,
                        )
                    )

        # Sort candidates by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    def find_best_candidate(
        self,
        html_content: str,
        target_field: str,
        old_selector: str | None = None,
    ) -> DOMCandidate | None:
        """Find the single most probable replacement element for a target field."""
        candidates = self.analyze(html_content, target_field=target_field)
        matching = [c for c in candidates if c.field_hint == target_field]

        if not matching:
            return None

        # Prefer candidates whose selector differs from the broken old_selector if provided
        if old_selector:
            diff_candidates = [c for c in matching if c.suggested_selector != old_selector]
            if diff_candidates:
                return diff_candidates[0]

        return matching[0]

    def _score_element(
        self,
        tag: str,
        classes: list[str],
        element_id: str | None,
        attrs: dict[str, str],
        text: str,
        target_field: str | None,
        parent_tag: str | None = None,
    ) -> tuple[str | None, float, str | None]:
        """Score an element to determine its field hint, match confidence, and reasoning."""
        scores: dict[str, float] = {"price": 0.0, "title": 0.0, "stock_status": 0.0}
        reasons: dict[str, list[str]] = {"price": [], "title": [], "stock_status": []}

        class_text = " ".join(classes).lower()
        id_text = (element_id or "").lower()

        # 1. Stock status scoring (check first so '2 left' is not counted as price)
        is_stock_text = bool(_STOCK_TEXT_RE.search(text))
        if is_stock_text:
            scores["stock_status"] += 0.50
            reasons["stock_status"].append(f"Matches inventory keyword '{text[:20]}'")
        if any(w in class_text for w in ("stock", "availab", "status", "inventory", "availability", "product-status", "instock")):
            scores["stock_status"] += 0.50
            reasons["stock_status"].append(f"Class matches stock semantics ({class_text[:20]})")
        if "stock" in id_text or "status" in id_text:
            scores["stock_status"] += 0.35
            reasons["stock_status"].append(f"ID matches stock semantics (#{id_text})")
        if attrs.get("data-testid") == "stock" or "stock" in attrs.get("data-testid", ""):
            scores["stock_status"] += 0.50
            reasons["stock_status"].append("data-testid matches stock")

        # 2. Price scoring
        if not is_stock_text:
            has_digits = any(ch.isdigit() for ch in text)
            has_currency = any(sym in text for sym in _CURRENCY_SYMBOLS)
            if _PRICE_VALUE_RE.search(text) and has_digits:
                scores["price"] += 0.50
                reasons["price"].append(f"Contains numeric price value '{text[:15]}'")
                if has_currency:
                    scores["price"] += 0.40
                    reasons["price"].append("Contains currency symbol")

            if any(w in class_text for w in ("price", "cost", "amount", "price_color", "rate", "current-price", "item-cost")):
                scores["price"] += 0.45
                reasons["price"].append(f"Class matches price semantics ({class_text[:20]})")
            if "price" in id_text:
                scores["price"] += 0.35
                reasons["price"].append(f"ID matches price semantics (#{id_text})")
            if attrs.get("data-testid") == "price" or "price" in attrs.get("data-testid", ""):
                scores["price"] += 0.50
                reasons["price"].append("data-testid matches price")

        # 3. Title scoring
        if tag in {"h1", "h2", "h3", "h4", "h5"}:
            scores["title"] += 0.65
            reasons["title"].append(f"Heading element <{tag}>")
        elif tag == "a" and parent_tag in {"h1", "h2", "h3", "h4", "h5"}:
            scores["title"] += 0.70
            reasons["title"].append(f"Link inside heading <{parent_tag}> > <a>")

        if any(w in class_text for w in ("title", "name", "product-name", "item-name", "product-title", "book-title")):
            scores["title"] += 0.45
            reasons["title"].append(f"Class matches title semantics ({class_text[:20]})")
        if "title" in id_text or "name" in id_text:
            scores["title"] += 0.35
            reasons["title"].append(f"ID matches title semantics (#{id_text})")
        if attrs.get("data-testid") == "title" or "title" in attrs.get("data-testid", ""):
            scores["title"] += 0.50
            reasons["title"].append("data-testid matches title")
        if text and len(text) > 3 and not text.startswith("$") and not text.startswith("£") and not is_stock_text:
            scores["title"] += 0.20

        # If a specific target_field was requested, evaluate that field
        if target_field and target_field in scores:
            score = min(round(scores[target_field], 2), 1.0)
            if score >= 0.3:
                reason_str = "; ".join(reasons[target_field]) or f"Matched heuristic for {target_field}"
                return target_field, score, reason_str

        # Otherwise pick the highest scoring field above threshold
        best_field = max(scores, key=scores.get)  # type: ignore
        best_score = min(round(scores[best_field], 2), 1.0)

        if best_score >= 0.4:
            reason_str = "; ".join(reasons[best_field]) or f"Matched heuristic for {best_field}"
            return best_field, best_score, reason_str

        return None, 0.0, None

    def _compute_selector(
        self,
        tag: str,
        classes: list[str],
        element_id: str | None,
        attrs: dict[str, str],
        parent_tag: str | None = None,
    ) -> str:
        """Derive a clean, robust CSS selector from element attributes."""
        # 1. Prefer data-testid or custom test attributes
        if attrs.get("data-testid"):
            return f"[data-testid='{attrs['data-testid']}']"
        if attrs.get("data-qa"):
            return f"[data-qa='{attrs['data-qa']}']"
        if attrs.get("data-cy"):
            return f"[data-cy='{attrs['data-cy']}']"

        # 2. Element ID
        if element_id:
            return f"#{element_id}"

        # 3. Specific semantic class names
        for cls in classes:
            lower = cls.lower()
            if any(key in lower for key in (
                "price_color", "current-price", "item-cost", "price", "cost", "amount",
                "product-name", "item-name", "product-title", "book-title", "title",
                "availability", "product-status", "instock", "inventory-status", "stock", "status"
            )):
                return f".{cls}"

        # 4. Heading link combination
        if tag == "a" and parent_tag in {"h1", "h2", "h3", "h4", "h5"}:
            return f"{parent_tag} a"

        # 5. First class name
        if classes:
            return f".{classes[0]}"

        # 6. Fallback to tag
        return tag

    def extract_with_selectors(
        self,
        html_content: str,
        selectors: dict[str, str],
    ) -> dict[str, str]:
        """Extract field values from HTML content using a map of field -> CSS selector."""
        if not html_content or not html_content.strip():
            return {field: "" for field in selectors}

        parser = _DOMElementParser()
        try:
            parser.feed(html_content)
        except Exception as exc:
            logger.error("Failed to parse HTML in extract_with_selectors: %s", exc)
            return {field: "" for field in selectors}

        extracted: dict[str, str] = {field: "" for field in selectors}

        for field, selector in selectors.items():
            sel = selector.strip()
            for elem in parser.elements:
                text = " ".join(elem["text_parts"]).strip()
                if elem["attributes"].get("title") and (not text or "..." in text):
                    text = elem["attributes"]["title"].strip()
                if not text:
                    continue

                matched = False
                # Match by data attribute ([data-testid='...'])
                if sel.startswith("[") and sel.endswith("]"):
                    attr_expr = sel[1:-1]
                    if "=" in attr_expr:
                        attr_name, attr_val = attr_expr.split("=", 1)
                        attr_val = attr_val.strip("\"'")
                        if elem["attributes"].get(attr_name) == attr_val:
                            matched = True
                    else:
                        if attr_expr in elem["attributes"]:
                            matched = True

                # Match by class (.class-name)
                elif sel.startswith("."):
                    target_cls = sel[1:].lower()
                    if any(c.lower() == target_cls for c in elem["classes"]):
                        matched = True

                # Match by ID (#element-id)
                elif sel.startswith("#"):
                    target_id = sel[1:].lower()
                    if (elem["element_id"] or "").lower() == target_id:
                        matched = True

                # Match by parent/child (e.g. 'h3 a')
                elif " " in sel:
                    parts = sel.split()
                    if len(parts) == 2 and elem["tag"] == parts[1].lower() and elem.get("parent_tag") == parts[0].lower():
                        matched = True

                # Match by tag name
                elif sel.lower() == elem["tag"]:
                    matched = True

                if matched:
                    if field == "price":
                        digits = "".join(ch for ch in text if ch.isdigit())
                        try:
                            val = float(digits) if digits else 0.0
                        except ValueError:
                            val = 0.0
                        if val > 0:
                            extracted[field] = text
                            break
                        elif not extracted[field]:
                            extracted[field] = text
                    else:
                        extracted[field] = text
                        break

        return extracted

    def extract_all_with_selectors(
        self,
        html_content: str,
        selectors: dict[str, str],
    ) -> list[dict[str, Any]]:
        """
        Extract all matching product records from HTML content using a map of selectors.

        Parses multi-card catalogs (e.g. books.toscrape, mock catalogs) as well as single product pages.
        """
        if not html_content or not html_content.strip():
            return []

        # 1. Check if mock parser extracts records
        try:
            from backend.scraper.mock_client import _MultiProductHTMLParser

            parser = _MultiProductHTMLParser(selectors=selectors)
            parser.feed(html_content)
            if parser.records:
                return parser.records
        except Exception:
            pass

        # 2. Generalized catalog card extractor (e.g. books.toscrape.com <article class="product_pod">)
        generalized_records = self._extract_generalized_catalog(html_content, selectors)
        if generalized_records:
            return generalized_records

        # 3. Fallback to single product extraction
        single = self.extract_with_selectors(html_content, selectors)
        if any(v for v in single.values()):
            return [single]

        return []

    def _extract_generalized_catalog(
        self,
        html_content: str,
        selectors: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Extract multi-item catalog by identifying container cards or repeated blocks."""
        parser = _DOMElementParser()
        try:
            parser.feed(html_content)
        except Exception:
            return []

        # Look for container items like <article class="product_pod">, <div class="product-card">, <li>
        cards: list[list[dict[str, Any]]] = []
        current_card: list[dict[str, Any]] | None = None

        card_indicators = {"product_pod", "product-card", "product-item", "item-card", "col-xs-6", "col-sm-4"}

        for elem in parser.elements:
            classes = elem["classes"]
            tag = elem["tag"]
            is_card_start = (
                tag == "article"
                or any(cls in card_indicators for cls in classes)
                or (tag == "li" and any("col-" in cls for cls in classes))
            )

            if is_card_start:
                if current_card:
                    cards.append(current_card)
                current_card = [elem]
            elif current_card is not None:
                current_card.append(elem)

        if current_card:
            cards.append(current_card)

        if not cards:
            return []

        records: list[dict[str, Any]] = []
        for card_elements in cards:
            record: dict[str, Any] = {
                "title": "",
                "price": "",
                "stock_status": "",
                "rating": None,
                "category": None,
                "product_url": None,
                "product_id": None,
            }

            for elem in card_elements:
                text = " ".join(elem["text_parts"]).strip()
                if elem["attributes"].get("title") and (not text or "..." in text):
                    text = elem["attributes"]["title"].strip()

                tag = elem["tag"]
                classes = elem["classes"]
                element_id = elem["element_id"]
                attrs = elem["attributes"]

                # Extract product link
                if tag == "a" and attrs.get("href") and not record["product_url"]:
                    record["product_url"] = attrs["href"]

                # Extract rating class if present (e.g. class="star-rating Three")
                if "star-rating" in classes or any("rating" in c for c in classes):
                    for cls in classes:
                        if cls in {"One", "Two", "Three", "Four", "Five", "1", "2", "3", "4", "5"}:
                            record["rating"] = cls

                # Match configured selectors
                for field, sel in selectors.items():
                    sel = sel.strip()
                    matched = False

                    if sel.startswith("[") and sel.endswith("]"):
                        attr_expr = sel[1:-1]
                        if "=" in attr_expr:
                            aname, aval = attr_expr.split("=", 1)
                            if attrs.get(aname) == aval.strip("\"'"):
                                matched = True
                    elif sel.startswith("."):
                        if any(c.lower() == sel[1:].lower() for c in classes):
                            matched = True
                    elif sel.startswith("#"):
                        if (element_id or "").lower() == sel[1:].lower():
                            matched = True
                    elif " " in sel:
                        parts = sel.split()
                        if len(parts) == 2 and tag == parts[1].lower() and elem.get("parent_tag") == parts[0].lower():
                            matched = True
                    elif sel.lower() == tag:
                        matched = True

                    if matched and text and not record.get(field):
                        record[field] = text

            if record.get("title") or record.get("price"):
                records.append(record)

        return records
