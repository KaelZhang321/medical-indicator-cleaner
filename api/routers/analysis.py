"""Analysis routes — quadrant analysis and ML features."""
from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException

from api.deps import get_cleaner, get_data_source, get_db, get_reference_ranges, get_risk_weights
from api.schemas import FeaturesResponse, QuadrantItem, QuadrantResponse, QuadrantStats
from src.risk_analyzer import calc_deviation, classify_quadrant

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.get("/exam/{study_id}/quadrant", response_model=QuadrantResponse)
def get_quadrant(study_id: str) -> QuadrantResponse:
    """Four-quadrant risk analysis for a single exam."""
    db = get_db()
    try:
        ds = get_data_source(db)
        df = ds.query_by_study_id(study_id)
    finally:
        db.close()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for study_id={study_id}")

    cleaner = get_cleaner()
    ref_df = get_reference_ranges()
    risk_df = get_risk_weights()

    # Build risk weight lookup
    risk_lookup: dict[str, float] = {}
    for _, row in risk_df.iterrows():
        try:
            risk_lookup[str(row["standard_code"])] = float(row["risk_weight"])
        except (ValueError, TypeError):
            pass

    quadrants: dict[str, list[QuadrantItem]] = {
        "紧急处理": [],
        "重点关注": [],
        "轻度异常": [],
        "正常范围": [],
    }

    for _, row in df.iterrows():
        item_name = str(row.get("item_name", "") or "")
        clean = cleaner.clean(item_name)
        code = clean.standard_code or str(row.get("item_code", ""))

        raw_val = row.get("result_value_raw")
        try:
            numeric = float(raw_val) if raw_val is not None else None
        except (ValueError, TypeError):
            numeric = None
        if numeric is not None and math.isnan(numeric):
            numeric = None

        if numeric is None:
            continue

        # Lookup reference range
        ref_min, ref_max = None, None
        if not ref_df.empty:
            ref_rows = ref_df[ref_df["standard_code"] == code]
            if not ref_rows.empty:
                r = ref_rows.iloc[0]
                ref_min = r.get("ref_min") if not (isinstance(r.get("ref_min"), float) and math.isnan(r.get("ref_min"))) else None
                ref_max = r.get("ref_max") if not (isinstance(r.get("ref_max"), float) and math.isnan(r.get("ref_max"))) else None

        if ref_min is None or ref_max is None:
            continue

        deviation = calc_deviation(numeric, ref_min, ref_max)
        risk_weight = risk_lookup.get(code, 0.3)
        quadrant = classify_quadrant(deviation, risk_weight)

        quadrants[quadrant].append(QuadrantItem(
            standard_name=clean.standard_name or clean.cleaned,
            standard_code=code,
            deviation=round(deviation, 3),
            risk_weight=risk_weight,
            value=numeric,
            ref_min=ref_min,
            ref_max=ref_max,
        ))

    stats = QuadrantStats(
        urgent_count=len(quadrants["紧急处理"]),
        watch_count=len(quadrants["重点关注"]),
        mild_count=len(quadrants["轻度异常"]),
        normal_count=len(quadrants["正常范围"]),
    )

    return QuadrantResponse(study_id=study_id, quadrants=quadrants, stats=stats)


@router.get("/patient/{sfzh}/features", response_model=FeaturesResponse)
def get_features(sfzh: str) -> FeaturesResponse:
    """Generate ML prediction features for a patient's exam history."""
    db = get_db()
    try:
        ds = get_data_source(db)
        frames = ds.query_by_patient(sfzh)
    finally:
        db.close()

    if not frames:
        raise HTTPException(status_code=404, detail="No exams found for this patient")

    cleaner = get_cleaner()

    # Sort by exam_time
    sorted_frames = sorted(frames, key=lambda f: str(f["exam_time"].iloc[0]) if not f.empty else "")
    latest = sorted_frames[-1]
    previous = sorted_frames[-2] if len(sorted_frames) > 1 else None

    features: dict[str, float | int | None] = {}
    abnormal_count = 0

    for _, row in latest.iterrows():
        item_name = str(row.get("item_name", "") or "")
        clean = cleaner.clean(item_name)
        code = clean.standard_code or str(row.get("item_code", ""))

        raw_val = row.get("result_value_raw")
        try:
            numeric = float(raw_val) if raw_val is not None else None
        except (ValueError, TypeError):
            numeric = None
        if numeric is not None and math.isnan(numeric):
            numeric = None

        if numeric is not None:
            features[f"{code}_latest"] = numeric

        if row.get("abnormal_flag") in (1, 2, "1", "2"):
            abnormal_count += 1

        # Change rate vs previous
        if previous is not None and numeric is not None:
            prev_rows = previous[previous["item_name"] == row.get("item_name")]
            if not prev_rows.empty:
                prev_raw = prev_rows.iloc[0].get("result_value_raw")
                try:
                    prev_val = float(prev_raw) if prev_raw is not None else None
                except (ValueError, TypeError):
                    prev_val = None
                if prev_val is not None and not math.isnan(prev_val) and prev_val != 0:
                    features[f"{code}_change_rate"] = round((numeric - prev_val) / prev_val, 4)

    features["abnormal_count"] = abnormal_count

    masked_id = sfzh[:4] + "****" + sfzh[-4:] if len(sfzh) > 8 else sfzh
    return FeaturesResponse(
        patient_id=masked_id,
        exam_count=len(sorted_frames),
        features=features,
    )
