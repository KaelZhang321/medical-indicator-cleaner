"""Merge LLM-generated and crawled data into the project's CSV data assets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils import ensure_dir, setup_logger

logger = setup_logger("merger")


class DataMerger:
    """Merge, deduplicate, and validate enrichment data before writing to CSV."""

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    def merge_aliases(
        self,
        standard_dict: pd.DataFrame,
        llm_aliases: dict[str, list[str]],
        crawled_aliases: dict[str, list[str]],
    ) -> pd.DataFrame:
        """Merge LLM and crawled aliases into standard_dict.aliases column.

        Priority: crawled > llm > original.  Duplicates removed.
        """
        updated = standard_dict.copy()
        for idx, row in updated.iterrows():
            code = row["code"]
            existing = [a.strip() for a in str(row.get("aliases", "")).split(";") if a.strip()]
            new_from_llm = llm_aliases.get(code, [])
            new_from_crawl = crawled_aliases.get(code, [])
            # Merge: existing + crawled + llm, deduplicated, preserve order
            combined = list(dict.fromkeys(existing + new_from_crawl + new_from_llm))
            updated.at[idx, "aliases"] = ";".join(combined)
        return updated

    # ------------------------------------------------------------------
    # Reference ranges
    # ------------------------------------------------------------------

    def merge_reference_ranges(
        self,
        llm_ranges: list[dict[str, Any]],
        crawled_ranges: list[dict[str, Any]],
        existing_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge LLM and crawled reference ranges. Crawled data wins on conflict.

        Returns a DataFrame in reference_range_standard.csv format.
        """
        # Index crawled data by standard_code
        crawled_by_code: dict[str, dict] = {}
        for item in crawled_ranges:
            code = item.get("standard_code", "")
            if code:
                crawled_by_code[code] = item

        rows: list[dict[str, Any]] = []
        seen_codes: set[str] = set()

        # Existing rows kept as-is
        for row in existing_df.itertuples(index=False):
            rows.append(row._asdict())
            seen_codes.add(row.standard_code)

        # Process LLM ranges, override with crawled if available
        for item in llm_ranges:
            code = item.get("standard_code", "")
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)

            crawled = crawled_by_code.get(code, {})
            general = item.get("general", {}) or {}
            ref_min = general.get("ref_min")
            ref_max = general.get("ref_max")

            # If crawled has data, prefer it
            if crawled.get("reference_ranges"):
                first_range = crawled["reference_ranges"][0]
                ref_min = first_range.get("ref_min", ref_min)
                ref_max = first_range.get("ref_max", ref_max)

            # Flag large discrepancies for review
            needs_review = ""
            if crawled.get("reference_ranges") and general.get("ref_min") is not None:
                c_min = crawled["reference_ranges"][0].get("ref_min")
                l_min = general.get("ref_min")
                if c_min is not None and l_min is not None and l_min != 0:
                    diff_pct = abs(c_min - l_min) / abs(l_min)
                    if diff_pct > 0.2:
                        needs_review = f"LLM={l_min}-{general.get('ref_max')}, crawled={c_min}-{crawled['reference_ranges'][0].get('ref_max')}"

            notes_parts = [item.get("notes", "")]
            if needs_review:
                notes_parts.append(f"REVIEW: {needs_review}")

            rows.append({
                "standard_code": code,
                "gender": "all",
                "age_min": 0,
                "age_max": 150,
                "ref_min": ref_min,
                "ref_max": ref_max,
                "unit": item.get("unit", ""),
                "notes": "; ".join(p for p in notes_parts if p),
            })

            # Add gender-specific rows if available
            for gender_key, gender_label in [("male", "male"), ("female", "female")]:
                gender_data = item.get(gender_key)
                if gender_data and gender_data.get("ref_min") is not None:
                    rows.append({
                        "standard_code": code,
                        "gender": gender_label,
                        "age_min": 18,
                        "age_max": 150,
                        "ref_min": gender_data["ref_min"],
                        "ref_max": gender_data.get("ref_max"),
                        "unit": item.get("unit", ""),
                        "notes": "",
                    })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Risk weights
    # ------------------------------------------------------------------

    def merge_risk_weights(
        self,
        llm_weights: list[dict[str, Any]],
        existing_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge LLM risk weights with existing data."""
        seen_codes = set(existing_df["standard_code"].tolist())
        rows = [row._asdict() for row in existing_df.itertuples(index=False)]

        for item in llm_weights:
            code = item.get("standard_code", "")
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            rows.append({
                "standard_code": code,
                "risk_weight": item.get("risk_weight", 0.5),
                "risk_category": item.get("risk_category", "info"),
                "notes": item.get("reason", ""),
            })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # New indicators
    # ------------------------------------------------------------------

    def merge_new_indicators(
        self,
        new_indicators: list[dict[str, Any]],
        existing_dict: pd.DataFrame,
        code_prefix: str = "NEW",
    ) -> pd.DataFrame:
        """Append new indicators to standard_dict, assigning temporary codes."""
        existing_names = set(existing_dict["standard_name"].tolist())
        existing_abbrs = set(existing_dict["abbreviation"].str.upper().tolist())
        rows = []
        counter = 1

        for item in new_indicators:
            name = item.get("standard_name", "").strip()
            abbr = item.get("abbreviation", "").strip()
            if not name:
                continue
            if name in existing_names or (abbr and abbr.upper() in existing_abbrs):
                logger.info("Skipping duplicate: %s (%s)", name, abbr)
                continue
            existing_names.add(name)
            if abbr:
                existing_abbrs.add(abbr.upper())

            rows.append({
                "code": f"{code_prefix}-{counter:03d}",
                "standard_name": name,
                "abbreviation": abbr,
                "aliases": item.get("aliases", ""),
                "category": item.get("category", ""),
                "common_unit": item.get("common_unit", ""),
                "result_type": item.get("result_type", "numeric"),
            })
            counter += 1

        if not rows:
            return existing_dict

        new_df = pd.DataFrame(rows)
        merged = pd.concat([existing_dict, new_df], ignore_index=True)
        logger.info("Added %d new indicators (total: %d)", len(rows), len(merged))
        return merged

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_standard_dict(self, df: pd.DataFrame) -> list[str]:
        """Check standard_dict for common issues."""
        issues: list[str] = []
        if df["code"].duplicated().any():
            dupes = df.loc[df["code"].duplicated(), "code"].tolist()
            issues.append(f"Duplicate codes: {dupes}")
        empty_names = df[df["standard_name"].fillna("").str.strip() == ""]
        if not empty_names.empty:
            issues.append(f"{len(empty_names)} rows with empty standard_name")
        # Check for double-semicolons in aliases
        bad_aliases = df[df["aliases"].fillna("").str.contains(";;")]
        if not bad_aliases.empty:
            issues.append(f"{len(bad_aliases)} rows with consecutive semicolons in aliases")
        return issues

    def validate_reference_ranges(self, df: pd.DataFrame) -> list[str]:
        issues: list[str] = []
        inverted = df[(df["ref_min"].notna()) & (df["ref_max"].notna()) & (df["ref_min"] > df["ref_max"])]
        if not inverted.empty:
            issues.append(f"{len(inverted)} rows with ref_min > ref_max")
        return issues

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load_json(path: str) -> Any:
        p = Path(path)
        if not p.exists():
            logger.warning("File not found: %s", path)
            return {} if path.endswith(".json") else []
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def save_csv(df: pd.DataFrame, path: str) -> None:
        ensure_dir(Path(path).parent)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("Saved %s (%d rows)", path, len(df))
