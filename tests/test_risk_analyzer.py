from __future__ import annotations

from src.risk_analyzer import calc_deviation, classify_quadrant


def test_calc_deviation_high() -> None:
    assert round(calc_deviation(7.0, 4.0, 6.0), 2) == 2.0


def test_calc_deviation_normal_center() -> None:
    assert calc_deviation(5.0, 4.0, 6.0) == 0.0


def test_classify_quadrant() -> None:
    quadrant = classify_quadrant(deviation=1.2, risk_weight=0.8)
    assert quadrant == "紧急处理"
