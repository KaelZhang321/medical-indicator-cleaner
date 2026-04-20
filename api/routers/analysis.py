"""Analysis routes — quadrant analysis and ML features."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from api.deps import get_cleaner, get_config, get_data_source, get_db, get_reference_ranges, get_risk_weights
from api.schemas import FeaturesResponse, FeaturesSummary, HealthScore, IndicatorFeature, QuadrantAdvice, QuadrantItem, QuadrantResponse, QuadrantStats
from scripts.build_ml_features import build_features
from src.quadrant_analyzer import QuadrantAnalyzer
from src.pipeline import StandardizationPipeline

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.get("/exam/{study_id}/quadrant", response_model=QuadrantResponse)
def get_quadrant(study_id: str) -> QuadrantResponse:
    """Four-quadrant risk analysis for a single exam using QuadrantAnalyzer v2."""
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
    analyzer = QuadrantAnalyzer()

    # Build indicator list for analyzer
    indicators: list[dict] = []
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

        indicators.append({
            "standard_code": code,
            "name": clean.standard_name or clean.cleaned,
            "category": clean.category or "",
            "value": numeric,
            "unit": str(row.get("unit_raw", "") or ""),
            "ref_min": ref_min,
            "ref_max": ref_max,
        })

    # Run analysis
    result = analyzer.analyze_exam(indicators)

    # Convert to response models
    def _to_item(d: dict) -> QuadrantItem:
        adv = d.get("advice", {})
        return QuadrantItem(
            standard_name=d.get("name", ""),
            standard_code=d.get("standard_code", ""),
            category=d.get("category", ""),
            deviation=d.get("deviation", 0.0),
            abs_deviation=d.get("abs_deviation", 0.0),
            direction=d.get("direction", "normal"),
            risk_weight=d.get("risk_weight", 0.0),
            quadrant=d.get("quadrant", "正常范围"),
            value=d.get("value"),
            unit=d.get("unit", ""),
            ref_min=d.get("ref_min"),
            ref_max=d.get("ref_max"),
            advice=QuadrantAdvice(
                summary=adv.get("summary", ""),
                action=adv.get("action", ""),
                urgency=adv.get("urgency", "routine"),
                details=adv.get("details", []),
            ),
        )

    quadrants = {q: [_to_item(i) for i in items] for q, items in result["quadrants"].items()}
    hs = result["health_score"]

    return QuadrantResponse(
        study_id=study_id,
        health_score=HealthScore(score=hs["score"], level=hs["level"], color=hs["color"]),
        quadrants=quadrants,
        stats=QuadrantStats(**result["stats"]),
        top_concerns=[_to_item(i) for i in result.get("top_concerns", [])],
        disclaimer=result.get("disclaimer", ""),
    )


@router.get("/patient/{sfzh}/features")
def get_features(sfzh: str):
    """Comprehensive health assessment using HealthAssessmentEngine."""
    from api.schemas import (
        DerivedIndicator, FeaturesResponse, FeaturesSummary,
        IndicatorFeature, SystemScore, TopRisk,
    )
    from src.health_assessment import HealthAssessmentEngine

    db = get_db()
    try:
        ds = get_data_source(db)
        frames = ds.query_by_patient(sfzh)
    finally:
        db.close()

    if not frames:
        raise HTTPException(status_code=404, detail="No exams found for this patient")

    # Filter to recent 3 years
    three_years_ago = (datetime.now() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
    sorted_frames = sorted(frames, key=lambda f: str(f["exam_time"].iloc[0]) if not f.empty else "")
    sorted_frames = [f for f in sorted_frames if not f.empty and str(f["exam_time"].iloc[0])[:10] >= three_years_ago]
    if not sorted_frames:
        raise HTTPException(status_code=404, detail="近三年内无体检数据")

    cleaner = get_cleaner()
    ref_df = get_reference_ranges()

    # Build exam_frames for HealthAssessmentEngine
    exam_frames: list[dict] = []
    for frame in sorted_frames:
        exam_time = str(frame["exam_time"].iloc[0]) if not frame.empty else ""
        indicators_map: dict[str, dict] = {}
        for _, row in frame.iterrows():
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
            if numeric is None or not code:
                continue
            indicators_map[code] = {
                "name": clean.standard_name or clean.cleaned,
                "value": numeric,
                "category": clean.category or "",
                "unit": str(row.get("unit_raw", "") or ""),
            }
        exam_frames.append({"exam_time": exam_time, "indicators": indicators_map})

    # Build ref_lookup
    ref_lookup: dict[str, tuple[float | None, float | None]] = {}
    if not ref_df.empty:
        for _, r in ref_df.iterrows():
            code = str(r.get("standard_code", ""))
            rmin = r.get("ref_min")
            rmax = r.get("ref_max")
            rmin = None if rmin is not None and isinstance(rmin, float) and math.isnan(rmin) else rmin
            rmax = None if rmax is not None and isinstance(rmax, float) and math.isnan(rmax) else rmax
            if code and code not in ref_lookup:
                ref_lookup[code] = (rmin, rmax)

    # Run assessment
    engine = HealthAssessmentEngine()
    report = engine.assess(exam_frames, ref_lookup)

    # Build indicator features (from latest exam with trend info)
    indicator_features: list[IndicatorFeature] = []
    if exam_frames:
        latest_inds = exam_frames[-1].get("indicators", {})
        prev_inds = exam_frames[-2].get("indicators", {}) if len(exam_frames) >= 2 else {}
        for code, info in latest_inds.items():
            ref = ref_lookup.get(code, (None, None))
            val = info["value"]
            is_abn = (ref[0] is not None and val < ref[0]) or (ref[1] is not None and val > ref[1])
            prev_val = prev_inds.get(code, {}).get("value")
            change_rate = None
            if prev_val is not None and prev_val != 0:
                change_rate = round((val - prev_val) / abs(prev_val), 4)
            trend = ""
            if change_rate is not None:
                trend = "上升" if change_rate > 0.05 else "下降" if change_rate < -0.05 else "稳定"
            # Risk level from top_risks
            risk_item = next((r for r in report.get("top_risks", []) if r["code"] == code), None)
            risk_level = risk_item["trend_type"] if risk_item else ("异常" if is_abn else "正常")
            indicator_features.append(IndicatorFeature(
                code=code, name=info["name"], category=info["category"],
                latest_value=val, previous_value=prev_val,
                change_rate=change_rate, is_abnormal=is_abn, trend=trend, risk_level=risk_level,
            ))
    indicator_features.sort(key=lambda i: (not i.is_abnormal, -abs(i.change_rate or 0)))

    # Count stats
    abnormal_count = sum(1 for i in indicator_features if i.is_abnormal)
    worsening = sum(1 for r in report.get("top_risks", []) if r.get("trend_type") in ("加速恶化", "减速恶化"))
    improving = len(report.get("positive_changes", []))

    masked_id = sfzh[:4] + "****" + sfzh[-4:] if len(sfzh) > 8 else sfzh
    return FeaturesResponse(
        patient_id=masked_id,
        exam_count=report.get("exam_count", len(sorted_frames)),
        time_span=report.get("time_span", ""),
        overall_score=report.get("overall_score", 100),
        overall_level=report.get("overall_level", "优秀"),
        overall_color=report.get("overall_color", "#52c41a"),
        summary=FeaturesSummary(
            total_indicators=len(indicator_features),
            abnormal_count=abnormal_count,
            worsening_count=worsening,
            improving_count=improving,
            overall_trend=report.get("overall_trend", "基本稳定"),
        ),
        system_scores=[SystemScore(**{k: v for k, v in s.items() if k != "weight"}) for s in report.get("system_scores", [])],
        derived_indicators=[DerivedIndicator(**d) for d in report.get("derived_indicators", [])],
        top_risks=[TopRisk(**r) for r in report.get("top_risks", [])],
        positive_changes=report.get("positive_changes", []),
        indicators=indicator_features,
        features={},
        disclaimer=report.get("disclaimer", ""),
    )
