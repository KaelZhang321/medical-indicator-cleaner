from __future__ import annotations

import re
from typing import Final


class ResultParser:
    UNIT_PATTERNS: Final[list[str]] = [
        r"kg/平方米",
        r"kcal",
        r"mmHg",
        r"bpm",
        r"kg",
        r"cm",
        r"ml",
        r"%",
        r"L",
    ]
    JUDGMENT_KEYWORDS: Final[list[str]] = ["偏低", "偏高", "正常", "异常"]
    QUALIFIER_PATTERN: Final[str] = r"^([<>≤≥])\s*"

    def parse(self, raw_value: str | None, existing_unit: str = "") -> dict[str, float | str | None]:
        result = self._empty_result()
        unit = (existing_unit or "").strip()
        result["unit"] = unit

        if raw_value is None:
            return result

        normalized = self._normalize_text(raw_value)
        if not normalized:
            return result

        normalized = self._extract_qualifier(normalized, result)

        comma_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*,\s*(.+)$", normalized)
        if comma_match:
            result["numeric_value"] = float(comma_match.group(1))
            trailing = comma_match.group(2).strip()
            if trailing in self.JUDGMENT_KEYWORDS:
                result["judgment"] = trailing
                return result
            result["text_value"] = self._clean_text_token(trailing)
            return result

        normalized = self._extract_reference_range(normalized, result)
        normalized = self._extract_judgment(normalized, result)

        if not unit:
            normalized = self._extract_unit(normalized, result)
        else:
            normalized = self._strip_trailing_unit_suffix(normalized, unit)

        paren_text_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*\(([^()]*)\)$", normalized)
        if paren_text_match:
            result["numeric_value"] = float(paren_text_match.group(1))
            text = self._extract_meaningful_text(paren_text_match.group(2))
            result["text_value"] = text
            return result

        text_with_paren_match = re.match(r"^(.+?)\s*\(([^()]*)\)$", normalized)
        if text_with_paren_match:
            base_text = self._clean_text_token(text_with_paren_match.group(1))
            paren_text = self._extract_meaningful_text(text_with_paren_match.group(2))
            result["text_value"] = base_text if base_text else paren_text
            return result

        if re.fullmatch(r"\d+\s*级", normalized):
            result["text_value"] = self._clean_text_token(normalized)
            return result

        numeric_with_text_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s+(.+)$", normalized)
        if numeric_with_text_match:
            trailing = self._clean_text_token(numeric_with_text_match.group(2))
            if self._looks_like_text_result(trailing):
                result["numeric_value"] = float(numeric_with_text_match.group(1))
                result["text_value"] = trailing
                return result

        if self._is_plain_numeric(normalized):
            result["numeric_value"] = float(normalized)
            return result

        prefixed_numeric_match = re.match(r"^([+-]?\d+(?:\.\d+)?)(?=[A-Za-z%/])", normalized)
        if prefixed_numeric_match and unit:
            result["numeric_value"] = float(prefixed_numeric_match.group(1))
            return result

        result["text_value"] = self._clean_text_token(normalized)
        return result

    def parse_reference_range(self, raw_ref: str | None) -> dict[str, object]:
        empty = {
            "ref_min": None,
            "ref_max": None,
            "ref_text": None,
            "ref_conditions": [],
            "is_simple_range": False,
        }
        text = self._normalize_text(raw_ref or "")
        if not text or text in {"~", "～", "-", "—"}:
            return empty

        condition_parts = re.split(r"[;；]", text)
        conditions = []
        for part in condition_parts:
            condition_match = re.match(r"^([^:：]+)[:：]\s*([+-]?\d+(?:\.\d+)?)\s*[-~～]\s*([+-]?\d+(?:\.\d+)?)$", part.strip())
            if condition_match:
                conditions.append(
                    {
                        "condition": condition_match.group(1).strip(),
                        "ref_min": float(condition_match.group(2)),
                        "ref_max": float(condition_match.group(3)),
                    }
                )
        if conditions:
            result = dict(empty)
            result["ref_conditions"] = conditions
            return result

        range_match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*[-~～]\s*([+-]?\d+(?:\.\d+)?)", text)
        if range_match:
            return {
                "ref_min": float(range_match.group(1)),
                "ref_max": float(range_match.group(2)),
                "ref_text": None,
                "ref_conditions": [],
                "is_simple_range": True,
            }

        less_than_match = re.fullmatch(r"<\s*([+-]?\d+(?:\.\d+)?)", text)
        if less_than_match:
            return {
                "ref_min": None,
                "ref_max": float(less_than_match.group(1)),
                "ref_text": None,
                "ref_conditions": [],
                "is_simple_range": True,
            }

        greater_than_match = re.fullmatch(r">\s*([+-]?\d+(?:\.\d+)?)", text)
        if greater_than_match:
            return {
                "ref_min": float(greater_than_match.group(1)),
                "ref_max": None,
                "ref_text": None,
                "ref_conditions": [],
                "is_simple_range": True,
            }

        result = dict(empty)
        result["ref_text"] = self._extract_meaningful_text(text) or self._clean_text_token(text)
        return result

    def _empty_result(self) -> dict[str, float | str | None]:
        return {
            "numeric_value": None,
            "text_value": None,
            "unit": "",
            "qualifier": None,
            "judgment": None,
            "ref_in_value": None,
        }

    def _normalize_text(self, raw_value: str) -> str:
        return (
            str(raw_value)
            .replace("（", "(")
            .replace("）", ")")
            .replace("，", ",")
            .strip()
        )

    def _extract_qualifier(self, text: str, result: dict[str, float | str | None]) -> str:
        match = re.match(self.QUALIFIER_PATTERN, text)
        if not match:
            return text
        qualifier = match.group(1)
        result["qualifier"] = "<" if qualifier == "≤" else ">" if qualifier == "≥" else qualifier
        return text[match.end() :].strip()

    def _extract_reference_range(self, text: str, result: dict[str, float | str | None]) -> str:
        match = re.search(r"\(([^()]*(?:\d[^()]*)?)\)", text)
        if not match:
            return text

        candidate = match.group(1).strip()
        if not self._looks_like_reference_range(candidate):
            return text

        result["ref_in_value"] = candidate
        return (text[: match.start()] + " " + text[match.end() :]).strip()

    def _extract_judgment(self, text: str, result: dict[str, float | str | None]) -> str:
        for keyword in self.JUDGMENT_KEYWORDS:
            if text.endswith(keyword):
                result["judgment"] = keyword
                return text[: -len(keyword)].strip()
        return text

    def _extract_unit(self, text: str, result: dict[str, float | str | None]) -> str:
        unit_pattern = "|".join(self.UNIT_PATTERNS)
        match = re.match(rf"^([+-]?\d+(?:\.\d+)?)\s*({unit_pattern})(.*)$", text)
        if not match:
            return text

        result["unit"] = match.group(2)
        remainder = match.group(3).strip()
        return f"{match.group(1)} {remainder}".strip()

    def _strip_trailing_unit_suffix(self, text: str, unit: str) -> str:
        escaped_unit = re.escape(unit)
        return re.sub(rf"^([+-]?\d+(?:\.\d+)?)\s*{escaped_unit}$", r"\1", text).strip()

    def _looks_like_reference_range(self, text: str) -> bool:
        if not text:
            return False
        if any(keyword in text for keyword in self.JUDGMENT_KEYWORDS):
            return False
        return bool(re.search(r"\d", text) and any(token in text for token in ["-", "~", "～", "<", ">"]))

    def _extract_meaningful_text(self, text: str) -> str | None:
        cleaned = self._clean_text_token(text)
        if cleaned in {"", "+", "-"}:
            return None
        if cleaned.startswith("阴性"):
            return "阴性"
        if cleaned.startswith("阳性"):
            return "阳性"
        return cleaned

    def _clean_text_token(self, text: str) -> str:
        cleaned = re.sub(r"\s+", "", str(text).strip())
        cleaned = re.sub(r"[+-]+$", "", cleaned)
        return cleaned

    def _looks_like_text_result(self, text: str) -> bool:
        if not text:
            return False
        if self._is_plain_numeric(text):
            return False
        return True

    def _is_plain_numeric(self, text: str) -> bool:
        return bool(re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text))
