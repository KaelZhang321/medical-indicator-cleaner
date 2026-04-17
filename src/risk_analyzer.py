from __future__ import annotations


def calc_deviation(value: float, ref_min: float, ref_max: float) -> float:
    mid = (ref_min + ref_max) / 2
    half_range = (ref_max - ref_min) / 2
    if half_range == 0:
        return 0.0
    return (value - mid) / half_range


def classify_quadrant(deviation: float, risk_weight: float) -> str:
    if risk_weight >= 0.7 and abs(deviation) >= 1:
        return "紧急处理"
    if risk_weight >= 0.7:
        return "重点关注"
    if abs(deviation) >= 1:
        return "轻度异常"
    return "正常范围"
