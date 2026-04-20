"""Calculate clinically derived composite indicators from basic lab values."""
from __future__ import annotations

import math
from typing import Any


# Derived indicator rules: each produces a ratio from two base indicators
DERIVED_RULES: dict[str, dict[str, Any]] = {
    "NLR": {
        "name": "中性粒细胞/淋巴细胞比值",
        "numerator_codes": ["030117", "030118"],  # NEU# or NEU absolute
        "denominator_codes": ["030116"],           # LYM#
        "ref_min": 1.0,
        "ref_max": 3.0,
        "risk_weight": 0.75,
        "clinical_high": "NLR升高提示全身炎症反应增强，与感染、肿瘤进展和心血管风险相关",
        "clinical_low": "NLR偏低较少见，可能提示免疫抑制状态",
    },
    "PLR": {
        "name": "血小板/淋巴细胞比值",
        "numerator_codes": ["030105"],   # PLT
        "denominator_codes": ["030116"], # LYM#
        "ref_min": 50.0,
        "ref_max": 150.0,
        "risk_weight": 0.65,
        "clinical_high": "PLR升高与炎症、血栓风险和肿瘤不良预后相关",
        "clinical_low": "",
    },
    "LDL_HDL_RATIO": {
        "name": "LDL/HDL比值",
        "numerator_codes": ["040204"],   # LDL-C
        "denominator_codes": ["040203"], # HDL-C
        "ref_min": 0.5,
        "ref_max": 2.5,
        "risk_weight": 0.80,
        "clinical_high": "LDL/HDL比值升高是动脉粥样硬化的核心风险指标",
        "clinical_low": "",
    },
    "AST_ALT_RATIO": {
        "name": "AST/ALT比值(De Ritis比)",
        "numerator_codes": ["040502"],   # AST
        "denominator_codes": ["040501"], # ALT
        "ref_min": 0.8,
        "ref_max": 1.2,
        "risk_weight": 0.65,
        "clinical_high": "De Ritis比>2.0提示酒精性肝病或肝硬化可能",
        "clinical_low": "",
    },
    "AG_RATIO": {
        "name": "白球比(A/G)",
        "numerator_codes": ["040506"],   # ALB
        "denominator_codes": ["040507"], # GLB
        "ref_min": 1.2,
        "ref_max": 2.4,
        "risk_weight": 0.60,
        "clinical_high": "",
        "clinical_low": "白球比降低提示肝脏合成功能下降或免疫球蛋白异常增多",
    },
}


class DerivedIndicatorEngine:
    """Calculate clinically meaningful derived indicators from base lab values."""

    def __init__(self, rules: dict[str, dict] | None = None) -> None:
        self.rules = rules or DERIVED_RULES

    def calculate(self, indicators: dict[str, float]) -> list[dict[str, Any]]:
        """Calculate all possible derived indicators from available base values.

        Args:
            indicators: {standard_code: numeric_value} mapping from a single exam

        Returns:
            List of derived indicator results
        """
        results: list[dict[str, Any]] = []

        for code, rule in self.rules.items():
            numerator = self._find_value(indicators, rule["numerator_codes"])
            denominator = self._find_value(indicators, rule["denominator_codes"])

            if numerator is None or denominator is None or denominator == 0:
                continue

            value = round(numerator / denominator, 2)
            ref_min = rule["ref_min"]
            ref_max = rule["ref_max"]

            if value > ref_max:
                status = "偏高"
                direction = "high"
                clinical = rule.get("clinical_high", "")
            elif value < ref_min:
                status = "偏低"
                direction = "low"
                clinical = rule.get("clinical_low", "")
            else:
                status = "正常"
                direction = "normal"
                clinical = ""

            results.append({
                "code": code,
                "name": rule["name"],
                "value": value,
                "ref_min": ref_min,
                "ref_max": ref_max,
                "status": status,
                "direction": direction,
                "risk_weight": rule["risk_weight"],
                "clinical": clinical,
            })

        return results

    @staticmethod
    def _find_value(indicators: dict[str, float], codes: list[str]) -> float | None:
        """Find first available value from a list of candidate codes."""
        for code in codes:
            val = indicators.get(code)
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                return val
        return None
