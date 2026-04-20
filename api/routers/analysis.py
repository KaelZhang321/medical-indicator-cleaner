"""Analysis routes — quadrant analysis and ML features."""
from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException

from api.deps import get_cleaner, get_data_source, get_db, get_reference_ranges, get_risk_weights
from api.schemas import FeaturesResponse, FeaturesSummary, IndicatorFeature, QuadrantItem, QuadrantResponse, QuadrantStats
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
    """Generate ML prediction features with clinical analysis for a patient."""
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

    # Sort by exam_time
    sorted_frames = sorted(frames, key=lambda f: str(f["exam_time"].iloc[0]) if not f.empty else "")
    latest = sorted_frames[-1]
    previous = sorted_frames[-2] if len(sorted_frames) > 1 else None

    features: dict[str, float | int | None] = {}
    indicators: list[IndicatorFeature] = []
    abnormal_count = 0
    worsening_count = 0
    improving_count = 0
    new_abnormal_count = 0
    stable_abnormal_count = 0

    for _, row in latest.iterrows():
        item_name = str(row.get("item_name", "") or "")
        clean = cleaner.clean(item_name)
        code = clean.standard_code or str(row.get("item_code", ""))
        name = clean.standard_name or clean.cleaned
        category = clean.category or ""

        raw_val = row.get("result_value_raw")
        try:
            numeric = float(raw_val) if raw_val is not None else None
        except (ValueError, TypeError):
            numeric = None
        if numeric is not None and math.isnan(numeric):
            numeric = None

        if numeric is None:
            continue

        features[f"{code}_latest"] = numeric
        is_abnormal = row.get("abnormal_flag") in (1, 2, "1", "2")
        if is_abnormal:
            abnormal_count += 1

        # Lookup reference range for context
        ref_min_val, ref_max_val = None, None
        if not ref_df.empty:
            ref_rows = ref_df[ref_df["standard_code"] == code]
            if not ref_rows.empty:
                rm = ref_rows.iloc[0].get("ref_min")
                rx = ref_rows.iloc[0].get("ref_max")
                ref_min_val = rm if rm is not None and not (isinstance(rm, float) and math.isnan(rm)) else None
                ref_max_val = rx if rx is not None and not (isinstance(rx, float) and math.isnan(rx)) else None

        # Compare with previous
        prev_val: float | None = None
        change_rate: float | None = None
        was_abnormal = False
        if previous is not None:
            prev_rows = previous[previous["item_name"] == row.get("item_name")]
            if not prev_rows.empty:
                prev_raw = prev_rows.iloc[0].get("result_value_raw")
                try:
                    prev_val = float(prev_raw) if prev_raw is not None else None
                except (ValueError, TypeError):
                    prev_val = None
                if prev_val is not None and math.isnan(prev_val):
                    prev_val = None
                if prev_val is not None and prev_val != 0:
                    change_rate = round((numeric - prev_val) / prev_val, 4)
                    features[f"{code}_change_rate"] = change_rate
                was_abnormal = prev_rows.iloc[0].get("abnormal_flag") in (1, 2, "1", "2")

        # Determine trend and risk_level
        trend = ""
        risk_level = ""
        if change_rate is not None:
            if change_rate > 0.05:
                trend = "上升"
            elif change_rate < -0.05:
                trend = "下降"
            else:
                trend = "稳定"

        # Clinical risk assessment
        if is_abnormal and not was_abnormal:
            risk_level = "新增异常"
            new_abnormal_count += 1
        elif is_abnormal and was_abnormal:
            if ref_max_val is not None and numeric > ref_max_val:
                if prev_val is not None and prev_val <= ref_max_val:
                    risk_level = "恶化"
                    worsening_count += 1
                elif change_rate is not None and change_rate > 0.1:
                    risk_level = "恶化"
                    worsening_count += 1
                else:
                    risk_level = "持续异常"
                    stable_abnormal_count += 1
            elif ref_min_val is not None and numeric < ref_min_val:
                if change_rate is not None and change_rate < -0.1:
                    risk_level = "恶化"
                    worsening_count += 1
                else:
                    risk_level = "持续异常"
                    stable_abnormal_count += 1
            else:
                risk_level = "持续异常"
                stable_abnormal_count += 1
        elif not is_abnormal and was_abnormal:
            risk_level = "改善"
            improving_count += 1
        else:
            risk_level = "正常"

        indicators.append(IndicatorFeature(
            code=code,
            name=name,
            category=category,
            latest_value=numeric,
            previous_value=prev_val,
            change_rate=change_rate,
            is_abnormal=is_abnormal,
            trend=trend,
            risk_level=risk_level,
        ))

    features["abnormal_count"] = abnormal_count

    # Overall trend
    if worsening_count > improving_count + 2:
        overall_trend = "整体恶化"
    elif improving_count > worsening_count + 2:
        overall_trend = "整体好转"
    else:
        overall_trend = "基本稳定"

    summary = FeaturesSummary(
        total_indicators=len(indicators),
        abnormal_count=abnormal_count,
        worsening_count=worsening_count,
        improving_count=improving_count,
        new_abnormal_count=new_abnormal_count,
        stable_abnormal_count=stable_abnormal_count,
        overall_trend=overall_trend,
    )

    # Sort: abnormal first, then by abs change_rate desc
    indicators.sort(key=lambda i: (not i.is_abnormal, -abs(i.change_rate or 0)))

    masked_id = sfzh[:4] + "****" + sfzh[-4:] if len(sfzh) > 8 else sfzh
    return FeaturesResponse(
        patient_id=masked_id,
        exam_count=len(sorted_frames),
        summary=summary,
        indicators=indicators,
        features=features,
    )
