"""Patient routes — history listing and longitudinal comparison."""
from __future__ import annotations

import math
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_cleaner, get_data_source, get_db, get_reference_ranges
from api.schemas import (
    ComparisonItem,
    ComparisonResponse,
    ExamListItem,
    PatientExamsResponse,
)

router = APIRouter(prefix="/api/v1", tags=["patient"])

TEXT_ITEM_KEYWORDS = ("超声", "结论", "所见", "描述", "提示", "检查", "影像", "PACS")
TEXT_SOURCE_TABLES = {"ods_tj_usb", "ods_tj_jlb"}


def _safe_float(value) -> float | None:
    try:
        numeric = float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
    if numeric is not None and math.isnan(numeric):
        return None
    return numeric


def _is_text_mode_row(row) -> bool:
    source_table = str(row.get("source_table", "") or "")
    item_name = str(row.get("item_name", "") or "")
    item_name_en = str(row.get("item_name_en", "") or "")
    raw_value = row.get("result_value_raw")
    text_value = str(raw_value or "").strip()
    if source_table in TEXT_SOURCE_TABLES:
        return True
    if any(keyword in item_name for keyword in TEXT_ITEM_KEYWORDS):
        return True
    if any(keyword in item_name_en for keyword in TEXT_ITEM_KEYWORDS):
        return True
    return isinstance(raw_value, str) and _safe_float(raw_value) is None and bool(text_value)


def _normalise_text_value(value) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _build_comparison_frames(frames, cleaner, category: Optional[str], mode: str, ref_df) -> tuple[dict[str, dict], list[str]]:
    merged: dict[str, dict] = {}
    all_dates: set[str] = set()

    for df in frames:
        for _, row in df.iterrows():
            item_name = str(row.get("item_name", "") or "")
            item_name_en = str(row.get("item_name_en", "") or "")
            clean = cleaner.clean(item_name)
            code = clean.standard_code or str(row.get("item_code", ""))
            name = clean.standard_name or clean.cleaned
            cat = clean.category or ""

            if category and cat != category:
                continue

            date_str = str(row.get("exam_time", "") or "")[:10]
            if not date_str:
                continue
            all_dates.add(date_str)

            if mode == "text":
                if not _is_text_mode_row(row):
                    continue
                raw_text = row.get("result_value_raw")
                if raw_text is None:
                    continue
                text = _normalise_text_value(raw_text)
                if not text:
                    continue
                if code not in merged:
                    merged[code] = {
                        "standard_code": code,
                        "standard_name": name,
                        "category": cat or "影像/结论",
                        "unit": "",
                        "values": {},
                        "ref_min": None,
                        "ref_max": None,
                    }
                merged[code]["values"][date_str] = text
                continue

            if _is_text_mode_row(row):
                continue

            raw_val = row.get("result_value_raw")
            numeric = _safe_float(raw_val)

            if code not in merged:
                ref_min, ref_max = None, None
                if not ref_df.empty:
                    ref_rows = ref_df[ref_df["standard_code"] == code]
                    if not ref_rows.empty:
                        ref_min = ref_rows.iloc[0].get("ref_min")
                        ref_max = ref_rows.iloc[0].get("ref_max")

                merged[code] = {
                    "standard_code": code,
                    "standard_name": name,
                    "category": cat,
                    "unit": str(row.get("unit_raw", "") or ""),
                    "values": {},
                    "ref_min": ref_min if ref_min is not None and not (isinstance(ref_min, float) and math.isnan(ref_min)) else None,
                    "ref_max": ref_max if ref_max is not None and not (isinstance(ref_max, float) and math.isnan(ref_max)) else None,
                }
            merged[code]["values"][date_str] = numeric

    return merged, sorted(all_dates)


def _build_comparison_items(merged: dict[str, dict], sorted_dates: list[str], mode: str) -> list[ComparisonItem]:
    comparisons: list[ComparisonItem] = []
    for info in merged.values():
        values = info["values"]
        trend = ""
        if mode == "text":
            ordered_values = [values.get(date) for date in sorted_dates if date in values]
            if len(ordered_values) >= 2:
                last_two = ordered_values[-2:]
                if last_two[0] != last_two[1]:
                    trend = "变化"
                elif last_two[0] is not None:
                    trend = "一致"
        else:
            if len(sorted_dates) >= 2:
                v1 = values.get(sorted_dates[-2])
                v2 = values.get(sorted_dates[-1])
                if v1 is not None and v2 is not None:
                    trend = "↑" if v2 > v1 else "↓" if v2 < v1 else "="

        comparisons.append(ComparisonItem(
            standard_code=info["standard_code"],
            standard_name=info["standard_name"],
            category=info["category"],
            unit=info["unit"],
            values=values,
            trend=trend,
            ref_min=info["ref_min"],
            ref_max=info["ref_max"],
        ))
    return comparisons


@router.get("/patient/{sfzh}/exams", response_model=PatientExamsResponse)
def list_patient_exams(sfzh: str) -> PatientExamsResponse:
    """List all exam visits for a patient."""
    db = get_db()
    try:
        ds = get_data_source(db)
        frames = ds.query_by_patient(sfzh)
    finally:
        db.close()

    if not frames:
        raise HTTPException(status_code=404, detail="No exams found for this patient")

    exams: list[ExamListItem] = []
    for df in frames:
        first = df.iloc[0]
        abnormal = int((df["abnormal_flag"].isin([1, 2, "1", "2"])).sum())
        exams.append(ExamListItem(
            study_id=str(first.get("study_id", "")),
            exam_time=str(first.get("exam_time", "") or ""),
            package_name=str(first.get("package_name", "") or ""),
            abnormal_count=abnormal,
        ))

    masked_id = sfzh[:4] + "****" + sfzh[-4:] if len(sfzh) > 8 else sfzh
    return PatientExamsResponse(
        patient_id=masked_id,
        exam_count=len(exams),
        exams=exams,
    )


@router.get("/patient/{sfzh}/comparison", response_model=ComparisonResponse)
def get_comparison(
    sfzh: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    mode: str = Query("numeric", pattern="^(numeric|text)$", description="Comparison mode"),
) -> ComparisonResponse:
    """Longitudinal comparison of indicators across all exams for a patient."""
    db = get_db()
    try:
        ds = get_data_source(db)
        frames = ds.query_by_patient(sfzh)
    finally:
        db.close()

    if not frames:
        raise HTTPException(status_code=404, detail="No exams found for this patient")

    cleaner = get_cleaner()
    ref_df = get_reference_ranges()
    merged, sorted_dates = _build_comparison_frames(frames, cleaner, category, mode, ref_df)
    comparisons = _build_comparison_items(merged, sorted_dates, mode)

    masked_id = sfzh[:4] + "****" + sfzh[-4:] if len(sfzh) > 8 else sfzh
    return ComparisonResponse(
        patient_id=masked_id,
        mode=mode,
        exam_dates=sorted_dates,
        comparisons=comparisons,
    )
