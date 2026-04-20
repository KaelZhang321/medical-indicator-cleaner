"""Comprehensive health assessment engine combining quadrant, trend, and derived indicators."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.derived_indicators import DerivedIndicatorEngine
from src.quadrant_analyzer import QuadrantAnalyzer
from src.trend_analyzer import TrendAnalyzer


class HealthAssessmentEngine:
    """Generate a comprehensive health report from multiple exam visits."""

    def __init__(
        self,
        body_systems_path: str = "data/body_systems.yaml",
        quadrant_analyzer: QuadrantAnalyzer | None = None,
    ) -> None:
        self.systems = self._load_systems(body_systems_path)
        self.trend_analyzer = TrendAnalyzer()
        self.derived_engine = DerivedIndicatorEngine()
        self.quadrant = quadrant_analyzer or QuadrantAnalyzer()

    @staticmethod
    def _load_systems(path: str) -> list[dict]:
        p = Path(path)
        if not p.exists():
            return []
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("systems", [])

    def assess(
        self,
        exam_frames: list[dict[str, Any]],
        ref_lookup: dict[str, tuple[float | None, float | None]],
    ) -> dict[str, Any]:
        """Run full health assessment across multiple exams.

        Args:
            exam_frames: list of exam dicts, each with:
                {"exam_time": str, "indicators": {code: {"name", "value", "category", "unit"}}}
                sorted by exam_time ascending
            ref_lookup: {standard_code: (ref_min, ref_max)}

        Returns:
            Comprehensive health report dict
        """
        if not exam_frames:
            return self._empty_report()

        latest_exam = exam_frames[-1]
        latest_time = latest_exam.get("exam_time", "")
        latest_indicators = latest_exam.get("indicators", {})

        # 1. Derived indicators from latest exam
        base_values = {code: info["value"] for code, info in latest_indicators.items()
                       if info.get("value") is not None}
        derived = self.derived_engine.calculate(base_values)

        # 2. Trend analysis for each indicator across exams
        trends: dict[str, dict] = {}
        for code in latest_indicators:
            series = []
            for exam in exam_frames:
                t = exam.get("exam_time", "")
                ind = exam.get("indicators", {}).get(code)
                if ind and ind.get("value") is not None:
                    series.append((t, ind["value"]))
            if series:
                ref = ref_lookup.get(code, (None, None))
                trends[code] = self.trend_analyzer.analyze(series, ref[0], ref[1])

        # 3. System-level assessment
        system_scores = []
        for sys_def in self.systems:
            sys_result = self._assess_system(sys_def, latest_indicators, derived, trends, ref_lookup)
            system_scores.append(sys_result)

        # 4. Overall score (weighted average of system scores)
        total_weight = sum(s["weight"] for s in system_scores) or 1.0
        overall_score = round(sum(s["score"] * s["weight"] for s in system_scores) / total_weight)
        overall_score = max(0, min(100, overall_score))

        # 5. Overall trend
        worsening = sum(1 for s in system_scores if s["trend"] in ("缓慢恶化", "加速恶化"))
        improving = sum(1 for s in system_scores if s["trend"] in ("持续改善", "拐点改善"))
        if worsening > improving + 1:
            overall_trend = "整体恶化"
        elif improving > worsening + 1:
            overall_trend = "整体好转"
        else:
            overall_trend = "基本稳定"

        # 6. Top risks (from trends)
        top_risks = self._build_top_risks(latest_indicators, trends, ref_lookup)

        # 7. Positive changes
        positive_changes = self._find_positive_changes(latest_indicators, trends, ref_lookup)

        # 8. Score level
        level, color = self._score_level(overall_score)

        time_span = ""
        if len(exam_frames) >= 2:
            first_time = str(exam_frames[0].get("exam_time", ""))[:10]
            last_time = str(exam_frames[-1].get("exam_time", ""))[:10]
            time_span = f"{first_time} ~ {last_time}"

        return {
            "overall_score": overall_score,
            "overall_level": level,
            "overall_color": color,
            "overall_trend": overall_trend,
            "exam_count": len(exam_frames),
            "time_span": time_span,
            "system_scores": system_scores,
            "top_risks": top_risks[:8],
            "positive_changes": positive_changes[:5],
            "derived_indicators": derived,
            "disclaimer": "以上评估基于体检数据的统计分析，仅供健康管理参考，不构成医疗诊断。具体治疗方案请遵医嘱。",
        }

    def _assess_system(
        self,
        sys_def: dict,
        latest_indicators: dict,
        derived: list[dict],
        trends: dict[str, dict],
        ref_lookup: dict,
    ) -> dict[str, Any]:
        """Assess a single body system."""
        sys_name = sys_def["name"]
        sys_key = sys_def["key"]
        sys_weight = sys_def.get("weight", 1.0)
        indicator_codes = sys_def.get("indicators", [])
        derived_codes = sys_def.get("derived", [])

        # Collect indicators belonging to this system
        system_indicators = []
        for code in indicator_codes:
            if code in latest_indicators:
                info = latest_indicators[code]
                ref = ref_lookup.get(code, (None, None))
                value = info.get("value")
                if value is None:
                    continue
                is_abnormal = False
                if ref[0] is not None and value < ref[0]:
                    is_abnormal = True
                if ref[1] is not None and value > ref[1]:
                    is_abnormal = True
                system_indicators.append({
                    "code": code,
                    "name": info.get("name", ""),
                    "value": value,
                    "is_abnormal": is_abnormal,
                    "trend": trends.get(code, {}),
                })

        # Collect relevant derived indicators
        system_derived = [d for d in derived if d["code"] in derived_codes]

        if not system_indicators:
            return {
                "system": sys_name, "key": sys_key, "weight": sys_weight,
                "score": 100, "status": "无数据", "trend": "稳定",
                "abnormal_count": 0, "worst_indicator": "",
                "key_findings": [], "recommendations": [],
            }

        # Score: start 100, deduct per abnormal
        score = 100
        abnormal_count = 0
        worst_name = ""
        worst_deviation = 0.0
        findings: list[str] = []
        recommendations: list[str] = []

        for ind in system_indicators:
            if ind["is_abnormal"]:
                abnormal_count += 1
                score -= 10
                trend_info = ind["trend"]
                trend_type = trend_info.get("trend_type", "稳定")

                if trend_type in ("加速恶化", "减速恶化"):
                    score -= 5
                if trend_info.get("consecutive_abnormal", 0) >= 3:
                    score -= 3

                # Track worst
                consec = trend_info.get("consecutive_abnormal", 0)
                if consec > worst_deviation:
                    worst_deviation = consec
                    worst_name = ind["name"]

                # Build finding
                latest = trend_info.get("latest_value", ind["value"])
                prev = trend_info.get("previous_value")
                if prev is not None:
                    change = f"（上次{prev}→本次{latest}）"
                else:
                    change = f"（当前值{latest}）"
                findings.append(f"{ind['name']}{change}，趋势：{trend_type}")

        # Derived indicator findings
        for d in system_derived:
            if d["status"] != "正常":
                score -= 5
                findings.append(f"{d['name']}={d['value']}，{d['status']}。{d.get('clinical', '')}")

        score = max(0, min(100, score))

        # Determine system status
        if score >= 90:
            status = "正常"
        elif score >= 70:
            status = "需关注"
        elif score >= 50:
            status = "异常"
        else:
            status = "危险"

        # System trend: aggregate indicator trends
        worsening = sum(1 for i in system_indicators
                        if i["trend"].get("trend_type", "") in ("加速恶化", "减速恶化"))
        improving = sum(1 for i in system_indicators
                        if i["trend"].get("trend_type", "") in ("持续改善", "拐点改善"))
        if worsening > improving:
            sys_trend = "缓慢恶化"
        elif improving > worsening:
            sys_trend = "持续改善"
        else:
            sys_trend = "稳定"

        return {
            "system": sys_name,
            "key": sys_key,
            "weight": sys_weight,
            "score": score,
            "status": status,
            "trend": sys_trend,
            "abnormal_count": abnormal_count,
            "worst_indicator": worst_name,
            "key_findings": findings[:5],
            "recommendations": recommendations[:3],
        }

    def _build_top_risks(
        self, latest_indicators: dict, trends: dict, ref_lookup: dict,
    ) -> list[dict]:
        """Build top risk list sorted by severity."""
        risks = []
        for code, trend in trends.items():
            info = latest_indicators.get(code, {})
            ref = ref_lookup.get(code, (None, None))
            value = info.get("value")
            if value is None:
                continue

            is_abnormal = False
            if ref[0] is not None and value < ref[0]:
                is_abnormal = True
            if ref[1] is not None and value > ref[1]:
                is_abnormal = True

            if not is_abnormal and trend.get("trend_type") == "稳定":
                continue

            # Risk score: higher = more urgent
            risk_score = 0
            if is_abnormal:
                risk_score += 3
            if trend.get("trend_type") in ("加速恶化",):
                risk_score += 3
            elif trend.get("trend_type") in ("减速恶化",):
                risk_score += 2
            elif trend.get("trend_type") == "波动不定":
                risk_score += 1
            risk_score += trend.get("consecutive_abnormal", 0)

            if risk_score > 0:
                risks.append({
                    "code": code,
                    "name": info.get("name", code),
                    "category": info.get("category", ""),
                    "value": value,
                    "unit": info.get("unit", ""),
                    "trend_type": trend.get("trend_type", ""),
                    "predicted_6m": trend.get("predicted_6m"),
                    "consecutive_abnormal": trend.get("consecutive_abnormal", 0),
                    "risk_score": risk_score,
                    "slope_direction": trend.get("slope_direction", ""),
                })

        risks.sort(key=lambda r: r["risk_score"], reverse=True)
        return risks

    def _find_positive_changes(
        self, latest_indicators: dict, trends: dict, ref_lookup: dict,
    ) -> list[str]:
        """Find indicators that are improving."""
        positives = []
        for code, trend in trends.items():
            info = latest_indicators.get(code, {})
            if trend.get("trend_type") in ("持续改善", "拐点改善"):
                name = info.get("name", code)
                latest = trend.get("latest_value")
                prev = trend.get("previous_value")
                if prev is not None and latest is not None:
                    positives.append(f"{name}改善：{prev} → {latest}")
                else:
                    positives.append(f"{name}呈改善趋势")
        return positives

    @staticmethod
    def _score_level(score: int) -> tuple[str, str]:
        if score >= 90:
            return "优秀", "#52c41a"
        if score >= 75:
            return "良好", "#1890ff"
        if score >= 60:
            return "一般", "#faad14"
        if score >= 40:
            return "较差", "#fa8c16"
        return "危险", "#ff4d4f"

    @staticmethod
    def _empty_report() -> dict[str, Any]:
        return {
            "overall_score": 0,
            "overall_level": "无数据",
            "overall_color": "#999",
            "overall_trend": "无数据",
            "exam_count": 0,
            "time_span": "",
            "system_scores": [],
            "top_risks": [],
            "positive_changes": [],
            "derived_indicators": [],
            "disclaimer": "",
        }
