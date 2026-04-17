from __future__ import annotations

import re
from dataclasses import dataclass

from tqdm import tqdm

from src.dict_manager import DictManager


FULLWIDTH_TRANSLATION = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "：": ":",
        "，": ",",
        "；": ";",
        "【": "[",
        "】": "]",
        "！": "!",
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
    }
)


@dataclass
class CleanResult:
    original: str
    cleaned: str
    abbreviation: str | None
    standard_name: str | None
    standard_code: str | None
    category: str | None
    confidence: float
    match_source: str


class L1RuleCleaner:
    """Apply deterministic rule-based cleaning before vector retrieval."""

    def __init__(self, dict_manager: DictManager) -> None:
        self.dict_manager = dict_manager

    def _strip(self, name: str) -> str:
        return str(name).strip()

    def _remove_star_prefix(self, name: str) -> str:
        return str(name).lstrip("★").lstrip()

    def _fullwidth_to_halfwidth(self, name: str) -> str:
        return str(name).translate(FULLWIDTH_TRANSLATION)

    def _extract_abbreviation_from_brackets(self, name: str) -> tuple[str, str | None]:
        normalized = str(name)
        match = re.match(r"^(.+?)\(([A-Za-z0-9\-\.βⅢ\s]+)\)$", normalized)
        if not match:
            return normalized, None
        return match.group(1).rstrip(), match.group(2).strip()

    def _remove_trailing_punctuation(self, name: str) -> str:
        return str(name).rstrip(".。,，、-_/")

    def _remove_internal_spaces(self, name: str) -> str:
        previous = str(name)
        while True:
            current = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", previous)
            if current == previous:
                return current
            previous = current

    def clean(self, item_name: str) -> CleanResult:
        original = "" if item_name is None else str(item_name)
        cleaned = self._strip(original)
        cleaned = self._remove_star_prefix(cleaned)
        cleaned = self._fullwidth_to_halfwidth(cleaned)
        cleaned, abbreviation = self._extract_abbreviation_from_brackets(cleaned)
        cleaned = self._remove_trailing_punctuation(cleaned)
        cleaned = self._remove_internal_spaces(cleaned)

        lookup = self.dict_manager.lookup(cleaned, abbreviation=abbreviation)
        if lookup:
            match_source = "abbr_exact" if abbreviation and abbreviation.upper() == cleaned.upper() else "alias_exact"
            return CleanResult(
                original=original,
                cleaned=cleaned,
                abbreviation=abbreviation,
                standard_name=lookup["standard_name"],
                standard_code=lookup["standard_code"],
                category=lookup["category"],
                confidence=1.0,
                match_source=match_source,
            )

        return CleanResult(
            original=original,
            cleaned=cleaned,
            abbreviation=abbreviation,
            standard_name=None,
            standard_code=None,
            category=None,
            confidence=0.0,
            match_source="unmatched",
        )

    def clean_major_item_name(self, name: str) -> str:
        cleaned = self._strip(name)
        cleaned = self._fullwidth_to_halfwidth(cleaned)
        if cleaned.startswith("H-"):
            cleaned = cleaned[2:]
        return self._strip(cleaned)

    def clean_batch(self, names: list[str]) -> list[CleanResult]:
        return [self.clean(name) for name in tqdm(names, desc="L1 cleaning", disable=len(names) < 2)]
