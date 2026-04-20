"""Four-quadrant health risk analysis engine (v2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


class QuadrantAnalyzer:
    """Analyze exam indicators into four quadrants with health scoring and advice."""

    def __init__(
        self,
        thresholds_path: str = "data/quadrant_thresholds.yaml",
        deviation_config_path: str = "data/deviation_config.csv",
        advice_rules_path: str = "data/health_advice_rules.yaml",
        risk_weight_path: str = "data/risk_weight.csv",
    ) -> None:
        self.thresholds = self._load_yaml(thresholds_path)
        self.deviation_config = self._load_deviation_config(deviation_config_path)
        self.advice_rules = self._load_yaml(advice_rules_path)
        self.risk_weights = self._load_risk_weights(risk_weight_path)

        self.dev_threshold = float(self.thresholds.get("deviation_threshold", 1.0))
        self.risk_threshold = float(self.thresholds.get("risk_threshold", 0.7))
        self.dev_cap = float(self.thresholds.get("deviation_cap", 3.0))
        self.score_penalties = self.thresholds.get("score_penalties", {})
        self.score_levels = self.thresholds.get("score_levels", [])

    @staticmethod
    def _load_yaml(path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _load_deviation_config(path: str) -> dict[str, dict]:
        p = Path(path)
        if not p.exists():
            return {}
        df = pd.read_csv(p, dtype=str).fillna("")
        config: dict[str, dict] = {}
        for _, row in df.iterrows():
            code = row.get("standard_code", "")
            if code:
                config[code] = {
                    "high_weight": float(row.get("high_weight", 1.0) or 1.0),
                    "low_weight": float(row.get("low_weight", 1.0) or 1.0),
                }
        return config

    @staticmethod
    def _load_risk_weights(path: str) -> dict[str, float]:
        p = Path(path)
        if not p.exists():
            return {}
        df = pd.read_csv(p, dtype=str).fillna("")
        weights: dict[str, float] = {}
        for _, row in df.iterrows():
            code = row.get("standard_code", "")
            try:
                weights[code] = float(row.get("risk_weight", 0.3))
            except (ValueError, TypeError):
                pass
        return weights

    def calc_deviation(
        self,
        value: float,
        ref_min: float,
        ref_max: float,
        standard_code: str = "",
    ) -> tuple[float, str]:
        """Calculate asymmetric weighted deviation.

        Returns (deviation, direction):
        - deviation: 0 = center of ref range, |1.0| = boundary, |>1| = out of range
        - direction: 'normal' | 'high' | 'low'
        """
        mid = (ref_min + ref_max) / 2
        half_range = (ref_max - ref_min) / 2
        if half_range == 0:
            return (0.0, "normal")

        raw = (value - mid) / half_range

        # Apply asymmetric weights
        cfg = self.deviation_config.get(standard_code, {})
        high_w = cfg.get("high_weight", 1.0)
        low_w = cfg.get("low_weight", 1.0)

        if raw > 0:
            deviation = raw * high_w
        else:
            deviation = raw * low_w

        # Determine direction
        if value > ref_max:
            direction = "high"
        elif value < ref_min:
            direction = "low"
        else:
            direction = "normal"

        # Cap
        deviation = max(-self.dev_cap, min(self.dev_cap, deviation))
        return (round(deviation, 3), direction)

    def get_risk_weight(self, standard_code: str) -> float:
        """Get risk weight for an indicator, default 0.3."""
        return self.risk_weights.get(standard_code, 0.3)

    def classify_quadrant(self, deviation: float, risk_weight: float) -> str:
        """Classify into 4 quadrants based on deviation and risk weight."""
        is_abnormal = abs(deviation) >= self.dev_threshold
        is_high_risk = risk_weight >= self.risk_threshold

        if is_high_risk and is_abnormal:
            return "紧急处理"
        if is_high_risk and not is_abnormal:
            return "重点关注"
        if not is_high_risk and is_abnormal:
            return "轻度异常"
        return "正常范围"

    def calc_health_score(self, quadrant_results: list[dict]) -> dict:
        """Calculate 0-100 health score from quadrant results.

        Returns: {"score": int, "level": str, "color": str}
        """
        score = 100
        for item in quadrant_results:
            quadrant = item.get("quadrant", "正常范围")
            penalty = self.score_penalties.get(quadrant, 0)
            score += penalty
        score = max(0, min(100, score))

        level = "危险"
        color = "#ff4d4f"
        for lvl in self.score_levels:
            if score >= lvl.get("min", 0):
                level = lvl.get("label", "")
                color = lvl.get("color", "#999")
                break

        return {"score": score, "level": level, "color": color}

    def generate_advice(
        self,
        name: str,
        category: str,
        value: float,
        unit: str,
        ref_min: float | None,
        ref_max: float | None,
        direction: str,
        quadrant: str,
    ) -> dict[str, str]:
        """Generate health advice for a single indicator.

        Returns: {"summary": str, "action": str, "urgency": str, "details": list[str]}
        """
        # Base advice from quadrant
        quadrant_rules = self.advice_rules.get("quadrant_advice", {})
        q_rule = quadrant_rules.get(quadrant, {})

        ref_range = ""
        if ref_min is not None and ref_max is not None:
            ref_range = f"{ref_min}-{ref_max}"
        elif ref_max is not None:
            ref_range = f"<{ref_max}"
        elif ref_min is not None:
            ref_range = f">{ref_min}"

        dir_text = "高" if direction == "high" else "低" if direction == "low" else ""

        summary = q_rule.get("template", "").format(
            name=name, value=value, unit=unit or "", ref_range=ref_range, direction=dir_text,
        )
        action = q_rule.get("action", "")
        urgency = q_rule.get("urgency", "routine")

        # Category-specific details
        details: list[str] = []
        cat_rules = self.advice_rules.get("category_advice", {}).get(category, {})
        dir_key = "high" if direction == "high" else "low" if direction == "low" else None
        if dir_key and dir_key in cat_rules:
            specific = cat_rules[dir_key]
            for key in ["diet", "exercise", "lifestyle", "follow_up", "specialist", "note"]:
                if key in specific:
                    label = {"diet": "饮食", "exercise": "运动", "lifestyle": "生活方式",
                             "follow_up": "复查", "specialist": "建议就诊科室", "note": "说明"}.get(key, key)
                    details.append(f"{label}：{specific[key]}")

        return {"summary": summary, "action": action, "urgency": urgency, "details": details}

    def analyze_indicator(
        self,
        standard_code: str,
        name: str,
        category: str,
        value: float,
        unit: str,
        ref_min: float | None,
        ref_max: float | None,
    ) -> dict[str, Any]:
        """Full analysis for a single indicator.

        Returns dict with: deviation, direction, risk_weight, quadrant, advice, etc.
        """
        if ref_min is None or ref_max is None:
            return {
                "standard_code": standard_code,
                "name": name,
                "category": category,
                "value": value,
                "unit": unit,
                "deviation": 0.0,
                "direction": "normal",
                "risk_weight": self.get_risk_weight(standard_code),
                "quadrant": "正常范围",
                "advice": {"summary": f"您的{name}缺少参考范围，无法评估", "action": "", "urgency": "routine", "details": []},
            }

        deviation, direction = self.calc_deviation(value, ref_min, ref_max, standard_code)
        risk_weight = self.get_risk_weight(standard_code)
        quadrant = self.classify_quadrant(deviation, risk_weight)
        advice = self.generate_advice(name, category, value, unit, ref_min, ref_max, direction, quadrant)

        return {
            "standard_code": standard_code,
            "name": name,
            "category": category,
            "value": value,
            "unit": unit,
            "ref_min": ref_min,
            "ref_max": ref_max,
            "deviation": deviation,
            "abs_deviation": round(abs(deviation), 3),
            "direction": direction,
            "risk_weight": risk_weight,
            "quadrant": quadrant,
            "advice": advice,
        }

    def analyze_exam(self, indicators: list[dict[str, Any]]) -> dict[str, Any]:
        """Full quadrant analysis for a complete exam.

        Args:
            indicators: list of dicts with keys:
                standard_code, name, category, value, unit, ref_min, ref_max

        Returns:
            {
                "quadrants": {"紧急处理": [...], ...},
                "health_score": {"score": int, "level": str, "color": str},
                "stats": {"urgent": int, "watch": int, "mild": int, "normal": int, "total": int},
                "top_concerns": [...],  # sorted by severity
                "disclaimer": str,
            }
        """
        results: list[dict] = []
        for ind in indicators:
            value = ind.get("value")
            if value is None:
                continue
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            result = self.analyze_indicator(
                standard_code=str(ind.get("standard_code", "")),
                name=str(ind.get("name", "")),
                category=str(ind.get("category", "")),
                value=value,
                unit=str(ind.get("unit", "")),
                ref_min=ind.get("ref_min"),
                ref_max=ind.get("ref_max"),
            )
            results.append(result)

        # Group by quadrant
        quadrants: dict[str, list] = {"紧急处理": [], "重点关注": [], "轻度异常": [], "正常范围": []}
        for r in results:
            q = r["quadrant"]
            quadrants.setdefault(q, []).append(r)

        # Health score
        health_score = self.calc_health_score(results)

        # Stats
        stats = {
            "urgent_count": len(quadrants["紧急处理"]),
            "watch_count": len(quadrants["重点关注"]),
            "mild_count": len(quadrants["轻度异常"]),
            "normal_count": len(quadrants["正常范围"]),
            "total": len(results),
        }

        # Top concerns: Q1 first sorted by |deviation| desc, then Q3
        top_concerns = sorted(
            quadrants["紧急处理"] + quadrants["轻度异常"],
            key=lambda x: x.get("abs_deviation", 0),
            reverse=True,
        )[:10]

        disclaimer = self.advice_rules.get("disclaimer", "以上建议仅供健康管理参考，不构成医疗诊断。")

        return {
            "quadrants": quadrants,
            "health_score": health_score,
            "stats": stats,
            "top_concerns": top_concerns,
            "disclaimer": disclaimer,
        }
