"""DOM analysis engine for inspecting HTML and identifying candidate elements."""

import logging
import re
from html.parser import HTMLParser
from typing import Any

from backend.automation.models import DOMCandidate

logger = logging.getLogger(__name__)

_PRICE_VALUE_RE = re.compile(r"[\$€£¥₹]?\s*\d+(?:[.,]\d+)?")
_STOCK_TEXT_RE = re.compile(r"\b(in stock|out of stock|available|unavailable|sold out|instock)\b", re.IGNORECASE)


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

        elem = {
            "tag": tag.lower(),
            "classes": classes,
            "element_id": element_id,
            "attributes": attr_dict,
            "text_parts": [],
        }
        self.elements.append(elem)
        self._tag_stack.append(elem)

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and self._tag_stack:
            self._tag_stack[-1]["text_parts"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack:
            self._tag_stack.pop()


class DOMAnalyzer:
    """
    Analyzes HTML content to find candidate DOM elements for failed fields.

    Finds candidate elements that represent missing fields (e.g. price, title, stock status)
    and computes suggested CSS selectors.
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

        for elem in parser.elements:
            text = " ".join(elem["text_parts"]).strip()
            tag = elem["tag"]
            classes = elem["classes"]
            element_id = elem["element_id"]
            attrs = elem["attributes"]

            if not text and not classes and not element_id:
                continue

            field_hint, confidence = self._score_element(tag, classes, element_id, attrs, text, target_field)

            if field_hint:
                selector = self._compute_selector(tag, classes, element_id, attrs)
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
    ) -> tuple[str | None, float]:
        """Score an element to determine its field hint and match confidence."""
        scores: dict[str, float] = {"price": 0.0, "title": 0.0, "stock_status": 0.0}

        class_text = " ".join(classes).lower()
        id_text = (element_id or "").lower()
        all_attr_text = " ".join(f"{k} {v}" for k, v in attrs.items()).lower()

        # 1. Price scoring
        if _PRICE_VALUE_RE.search(text) and any(ch.isdigit() for ch in text):
            scores["price"] += 0.5
            if "$" in text or "€" in text or "£" in text or "USD" in text:
                scores["price"] += 0.3
        if "price" in class_text or "cost" in class_text or "amount" in class_text:
            scores["price"] += 0.4
        if "price" in id_text or "price" in all_attr_text:
            scores["price"] += 0.3

        # 2. Title scoring
        if tag in {"h1", "h2", "h3", "h4"}:
            scores["title"] += 0.4
        if "title" in class_text or "product-name" in class_text or "item-name" in class_text:
            scores["title"] += 0.5
        if "title" in id_text or "name" in id_text:
            scores["title"] += 0.3
        if text and len(text) > 3 and tag in {"h1", "h2", "h3", "p", "span"}:
            scores["title"] += 0.1

        # 3. Stock status scoring
        if _STOCK_TEXT_RE.search(text):
            scores["stock_status"] += 0.6
        if "stock" in class_text or "availab" in class_text or "status" in class_text:
            scores["stock_status"] += 0.4
        if "stock" in id_text or "status" in id_text:
            scores["stock_status"] += 0.3

        # If a specific target_field was requested, boost that field's relevance
        if target_field and target_field in scores:
            score = scores[target_field]
            if score >= 0.3:
                return target_field, min(round(score, 2), 1.0)

        # Otherwise pick the highest scoring field above threshold
        best_field = max(scores, key=scores.get)  # type: ignore
        best_score = scores[best_field]

        if best_score >= 0.4:
            return best_field, min(round(best_score, 2), 1.0)

        return None, 0.0

    def _compute_selector(
        self,
        tag: str,
        classes: list[str],
        element_id: str | None,
        attrs: dict[str, str],
    ) -> str:
        """Derive a clean CSS selector from element attributes."""
        if element_id:
            return f"#{element_id}"

        for cls in classes:
            if any(key in cls.lower() for key in ("price", "title", "status", "stock", "product", "item")):
                return f".{cls}"

        if classes:
            return f".{classes[0]}"

        for key, val in attrs.items():
            if key.startswith("data-") or key in {"itemprop", "name"}:
                return f"[{key}='{val}']" if val else f"[{key}]"

        return tag

    def extract_with_selectors(
        self,
        html_content: str,
        selectors: dict[str, str],
    ) -> dict[str, str]:
        """
        Extract field values from HTML content using a map of field -> CSS selector.

        Supports class (.name), ID (#id), attribute ([attr='val']), and tag selectors.
        """
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
                if not text:
                    continue

                # Match by class (.class-name)
                if sel.startswith("."):
                    target_cls = sel[1:].lower()
                    if any(c.lower() == target_cls for c in elem["classes"]):
                        extracted[field] = text
                        break

                # Match by ID (#element-id)
                elif sel.startswith("#"):
                    target_id = sel[1:].lower()
                    if (elem["element_id"] or "").lower() == target_id:
                        extracted[field] = text
                        break

                # Match by tag name
                elif sel.lower() == elem["tag"]:
                    extracted[field] = text
                    break

                # Match by attribute ([attr] or [attr='val'])
                elif sel.startswith("[") and sel.endswith("]"):
                    attr_expr = sel[1:-1]
                    if "=" in attr_expr:
                        attr_name, attr_val = attr_expr.split("=", 1)
                        attr_val = attr_val.strip("\"'")
                        if elem["attributes"].get(attr_name) == attr_val:
                            extracted[field] = text
                            break
                    else:
                        if attr_expr in elem["attributes"]:
                            extracted[field] = text
                            break

        return extracted

