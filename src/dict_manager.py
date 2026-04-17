from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


STANDARD_REQUIRED_COLUMNS = {
    "code",
    "standard_name",
    "abbreviation",
    "aliases",
    "category",
    "common_unit",
    "result_type",
}

ALIAS_REQUIRED_COLUMNS = {"alias", "standard_code", "source", "added_date"}


@dataclass(frozen=True)
class StandardRecord:
    code: str
    standard_name: str
    category: str

    def to_lookup_result(self) -> dict[str, str]:
        return {
            "standard_code": self.code,
            "standard_name": self.standard_name,
            "category": self.category,
        }


class DictManager:
    def __init__(self, standard_dict_path: str, alias_dict_path: str) -> None:
        self.standard_dict_path = Path(standard_dict_path)
        self.alias_dict_path = Path(alias_dict_path)
        self.standard_dict = self._load_standard_dict(self.standard_dict_path)
        self.alias_dict = self._load_alias_dict(self.alias_dict_path)
        self.standard_code_map = self._build_standard_code_map()
        self.name_to_code: dict[str, dict[str, str]] = {}
        self.abbr_to_code: dict[str, dict[str, str]] = {}
        self.name_upper_to_code: dict[str, dict[str, str]] = {}
        self._build_lookup_index()

    def _load_standard_dict(self, path: str | Path) -> pd.DataFrame:
        df = pd.read_csv(path, dtype=str).fillna("")
        missing_columns = STANDARD_REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"standard_dict missing required columns: {missing}")
        return df

    def _load_alias_dict(self, path: str | Path) -> pd.DataFrame:
        df = pd.read_csv(path, dtype=str).fillna("")
        missing_columns = ALIAS_REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"alias_dict missing required columns: {missing}")
        return df

    def _build_standard_code_map(self) -> dict[str, StandardRecord]:
        record_map: dict[str, StandardRecord] = {}
        for row in self.standard_dict.itertuples(index=False):
            record_map[row.code] = StandardRecord(
                code=row.code,
                standard_name=row.standard_name,
                category=row.category,
            )
        return record_map

    def _build_lookup_index(self) -> None:
        self.name_to_code = {}
        self.abbr_to_code = {}
        self.name_upper_to_code = {}

        for row in self.standard_dict.itertuples(index=False):
            payload = self._payload_from_code(row.code)
            self._register_name(row.standard_name, payload)

            if row.abbreviation:
                abbreviation = row.abbreviation.upper()
                self.abbr_to_code[abbreviation] = payload
                self.name_upper_to_code[abbreviation] = payload

            for alias in self._split_aliases(row.aliases):
                self._register_name(alias, payload)

        for row in self.alias_dict.itertuples(index=False):
            alias = str(row.alias).strip()
            standard_code = str(row.standard_code).strip()
            if not alias or not standard_code:
                continue
            payload = self._payload_from_code(standard_code)
            self._register_name(alias, payload)

    def _payload_from_code(self, standard_code: str) -> dict[str, str]:
        try:
            record = self.standard_code_map[standard_code]
        except KeyError as exc:
            raise ValueError(f"Unknown standard_code in alias dictionary: {standard_code}") from exc
        return record.to_lookup_result()

    def _register_name(self, name: str, payload: dict[str, str]) -> None:
        normalized = str(name).strip()
        if not normalized:
            return
        self.name_to_code[normalized] = payload
        self.name_upper_to_code[normalized.upper()] = payload

    def _split_aliases(self, aliases: str) -> list[str]:
        return [part.strip() for part in str(aliases).split(";") if part.strip()]

    def lookup(self, cleaned_name: str, abbreviation: str | None = None) -> dict[str, str] | None:
        normalized_name = str(cleaned_name).strip()
        if normalized_name in self.name_to_code:
            return self.name_to_code[normalized_name]

        if abbreviation:
            normalized_abbr = str(abbreviation).strip().upper()
            if normalized_abbr in self.abbr_to_code:
                return self.abbr_to_code[normalized_abbr]

        if normalized_name.upper() in self.name_upper_to_code:
            return self.name_upper_to_code[normalized_name.upper()]

        return None

    def add_alias(self, alias: str, standard_code: str, source: str = "manual_review") -> None:
        normalized_alias = str(alias).strip()
        if not normalized_alias:
            return

        if normalized_alias in self.name_to_code or normalized_alias.upper() in self.name_upper_to_code:
            return

        payload = self._payload_from_code(standard_code)
        new_row = pd.DataFrame(
            [
                {
                    "alias": normalized_alias,
                    "standard_code": standard_code,
                    "source": source,
                    "added_date": date.today().isoformat(),
                }
            ]
        )
        self.alias_dict = pd.concat([self.alias_dict, new_row], ignore_index=True)
        self._register_name(normalized_alias, payload)
        self.save_alias_dict()

    def save_alias_dict(self) -> None:
        self.alias_dict.to_csv(self.alias_dict_path, index=False)
