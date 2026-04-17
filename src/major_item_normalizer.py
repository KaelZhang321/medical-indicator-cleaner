from __future__ import annotations

import pandas as pd


class MajorItemNormalizer:
    """Normalize major item/package names using a small dictionary."""

    def __init__(self, dict_path: str) -> None:
        self.dict_df = pd.read_csv(dict_path, dtype=str).fillna("")
        self.lookup_index: dict[str, dict[str, str]] = {}
        for row in self.dict_df.itertuples(index=False):
            self.lookup_index[row.standard_name] = self._payload(row)
            for alias in str(row.aliases).split(";"):
                normalized = alias.strip()
                if normalized:
                    self.lookup_index[normalized] = self._payload(row)
        self.substring_index = sorted(self.lookup_index.items(), key=lambda item: -len(item[0]))

    def _payload(self, row) -> dict[str, str]:
        return {
            "major_item_standard_code": row.code,
            "major_item_standard_name": row.standard_name,
            "major_item_category": row.category,
        }

    def lookup(self, name: str) -> dict[str, str] | None:
        normalized = str(name).replace("（", "(").replace("）", ")").strip()
        if normalized.startswith("H-"):
            normalized = normalized[2:]
        if normalized in self.lookup_index:
            return self.lookup_index[normalized]
        for alias, payload in self.substring_index:
            if alias and alias in normalized:
                return payload
        return None
