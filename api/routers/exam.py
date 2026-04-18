"""Exam query routes — single visit lookup."""
from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException

from api.deps import get_cleaner, get_data_source, get_db
from api.schemas import ExamResponse, ExamSummary, IndicatorResult

router = APIRouter(prefix="/api/v1", tags=["exam"])


def _safe_value(val) -> float | str | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


@router.get("/exam/{study_id}", response_model=ExamResponse)
def get_exam(study_id: str) -> ExamResponse:
    """Query standardized exam results for a single visit."""
    db = get_db()
    try:
        ds = get_data_source(db)
        df = ds.query_by_study_id(study_id)
    finally:
        db.close()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for study_id={study_id}")

    cleaner = get_cleaner()
    indicators: list[IndicatorResult] = []

    for _, row in df.iterrows():
        item_name = str(row.get("item_name", "") or "")
        clean = cleaner.clean(item_name)

        indicators.append(IndicatorResult(
            standard_code=clean.standard_code or str(row.get("item_code", "")),
            standard_name=clean.standard_name or clean.cleaned,
            category=clean.category or "",
            value=_safe_value(row.get("result_value_raw")),
            unit=str(row.get("unit_raw", "") or ""),
            reference_range=str(row.get("reference_range_raw", "") or ""),
            is_abnormal=row.get("abnormal_flag") in (1, 2, "1", "2"),
            abnormal_direction="high" if row.get("abnormal_flag") in (2, "2") else "low" if row.get("abnormal_flag") in (1, "1") else None,
        ))

    abnormal_count = sum(1 for i in indicators if i.is_abnormal)
    categories = sorted(set(i.category for i in indicators if i.category))

    first_row = df.iloc[0]
    return ExamResponse(
        study_id=study_id,
        patient_name=str(first_row.get("patient_name", "") or ""),
        gender=str(first_row.get("gender", "") or ""),
        exam_time=str(first_row.get("exam_time", "") or ""),
        package_name=str(first_row.get("package_name", "") or ""),
        summary=ExamSummary(
            total_indicators=len(indicators),
            abnormal_count=abnormal_count,
            categories=categories,
        ),
        indicators=indicators,
    )
