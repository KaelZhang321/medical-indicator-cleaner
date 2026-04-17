from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.abnormal_detector import derive_abnormal_status
from src.result_parser import ResultParser
from src.unit_normalizer import UnitNormalizer
from src.utils import setup_logger


class P0Preprocessor:
    """Preprocess HIS JSON data into a flat indicator dataframe."""

    DEFAULT_WHITELIST = {"HY", "YB", "ER"}

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        departments = config.get("departments", {})
        preprocessing = config.get("preprocessing", {})
        self.dept_whitelist = set(departments.get("whitelist", self.DEFAULT_WHITELIST))
        self.enable_deduplicate = bool(preprocessing.get("deduplicate", True))
        self.enable_result_parse = bool(preprocessing.get("parse_result_value", True))
        self.result_parser = ResultParser()
        self.unit_normalizer = UnitNormalizer()
        self.logger = setup_logger(self.__class__.__name__)

    def _flatten_items(self, json_data: dict[str, Any]) -> pd.DataFrame:
        """Flatten HIS nested departments/items JSON into row records."""
        data = json_data.get("data", {})
        rows: list[dict[str, Any]] = []

        for department in data.get("departments", []):
            for item in department.get("items", []):
                rows.append(
                    {
                        "study_id": data.get("studyId"),
                        "exam_time": data.get("examTime"),
                        "package_name": data.get("packageName"),
                        "dept_code": department.get("departmentCode"),
                        "dept_name": department.get("departmentName"),
                        "source_table": department.get("sourceTable"),
                        "major_item_code": item.get("majorItemCode"),
                        "major_item_name": item.get("majorItemName"),
                        "item_code": item.get("itemCode"),
                        "item_name": item.get("itemName"),
                        "item_name_en": item.get("itemNameEn"),
                        "result_value_raw": item.get("resultValue"),
                        "unit_raw": item.get("unit"),
                        "reference_range_raw": item.get("referenceRange"),
                        "abnormal_flag": item.get("abnormalFlag"),
                    }
                )

        return pd.DataFrame(
            rows,
            columns=[
                "study_id",
                "exam_time",
                "package_name",
                "dept_code",
                "dept_name",
                "source_table",
                "major_item_code",
                "major_item_name",
                "item_code",
                "item_name",
                "item_name_en",
                "result_value_raw",
                "unit_raw",
                "reference_range_raw",
                "abnormal_flag",
            ],
        )

    def _filter_departments(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep only configured department whitelist rows."""
        before = len(df)
        filtered = df.loc[df["dept_code"].isin(self.dept_whitelist)].copy()
        removed = sorted(set(df["dept_code"].dropna()) - set(filtered["dept_code"].dropna()))
        self.logger.info(
            "Filtered departments: before=%s after=%s removed=%s",
            before,
            len(filtered),
            ",".join(removed) if removed else "none",
        )
        return filtered

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop duplicate indicators while keeping the first row."""
        before = len(df)
        deduplicated = df.drop_duplicates(
            subset=["study_id", "dept_code", "item_code", "item_name"],
            keep="first",
        ).copy()
        self.logger.info(
            "Deduplicated rows: before=%s after=%s removed=%s",
            before,
            len(deduplicated),
            before - len(deduplicated),
        )
        return deduplicated

    def process(self, json_data: dict[str, Any]) -> pd.DataFrame:
        """Run flatten, filter, deduplicate, and result-value parsing."""
        df = self._flatten_items(json_data)
        df = self._filter_departments(df)

        if self.enable_deduplicate:
            df = self._deduplicate(df)

        if not self.enable_result_parse:
            return df

        parsed_records = [
            self.result_parser.parse(row.result_value_raw, row.unit_raw or "")
            for row in df.itertuples(index=False)
        ]
        reference_records = [
            self.result_parser.parse_reference_range(row.reference_range_raw)
            for row in df.itertuples(index=False)
        ]
        parsed_df = pd.DataFrame(parsed_records)
        parsed_df = parsed_df.rename(columns={"unit": "unit_parsed"})
        reference_df = pd.DataFrame(reference_records)

        result = pd.concat(
            [df.reset_index(drop=True), parsed_df.reset_index(drop=True), reference_df.reset_index(drop=True)],
            axis=1,
        )
        result["unit"] = result["unit_raw"].fillna("").astype(str).str.strip()
        unit_missing = result["unit"] == ""
        result.loc[unit_missing, "unit"] = result.loc[unit_missing, "unit_parsed"]
        result["unit"] = result["unit"].apply(self.unit_normalizer.normalize)
        abnormal_records = [
            derive_abnormal_status(
                row.numeric_value if pd.notna(row.numeric_value) else None,
                row.ref_min if pd.notna(row.ref_min) else None,
                row.ref_max if pd.notna(row.ref_max) else None,
                row.abnormal_flag,
            )
            for row in result.itertuples(index=False)
        ]
        abnormal_df = pd.DataFrame(abnormal_records)
        abnormal_df = abnormal_df.astype(object).where(pd.notna(abnormal_df), None)
        result = pd.concat([result.reset_index(drop=True), abnormal_df.reset_index(drop=True)], axis=1)
        return result

    def process_file(self, json_path: str) -> pd.DataFrame:
        """Read one JSON file and process it into a dataframe."""
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        return self.process(data)

    def process_batch(self, json_paths: list[str]) -> pd.DataFrame:
        """Process multiple JSON files and concatenate the results."""
        frames = [self.process_file(path) for path in json_paths]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)
