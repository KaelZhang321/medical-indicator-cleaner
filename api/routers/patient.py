"""Patient routes — history listing and longitudinal comparison."""
from __future__ import annotations

import math
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
def get_comparison(sfzh: str, category: Optional[str] = Query(None, description="Filter by category")) -> ComparisonResponse:
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

    # Build: {standard_code: {info + date→value}}
    merged: dict[str, dict] = {}
    all_dates: set[str] = set()

    for df in frames:
        for _, row in df.iterrows():
            item_name = str(row.get("item_name", "") or "")
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

            raw_val = row.get("result_value_raw")
            try:
                numeric = float(raw_val) if raw_val is not None else None
            except (ValueError, TypeError):
                numeric = None
            if numeric is not None and math.isnan(numeric):
                numeric = None

            if code not in merged:
                # Lookup reference range
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

    # Compute trends
    comparisons: list[ComparisonItem] = []
    sorted_dates = sorted(all_dates)
    for info in merged.values():
        values = info["values"]
        trend = ""
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

    masked_id = sfzh[:4] + "****" + sfzh[-4:] if len(sfzh) > 8 else sfzh
    return ComparisonResponse(
        patient_id=masked_id,
        exam_dates=sorted_dates,
        comparisons=comparisons,
    )
