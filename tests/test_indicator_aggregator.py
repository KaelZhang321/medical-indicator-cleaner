from __future__ import annotations

import pandas as pd

from src.indicator_aggregator import IndicatorAggregator


def test_aggregate_hpv_any_positive() -> None:
    df = pd.DataFrame(
        [
            {"major_item_standard_name": "HPV核酸检测", "item_name": "HPV16", "text_value": "阳性", "numeric_value": None},
            {"major_item_standard_name": "HPV核酸检测", "item_name": "HPV18", "text_value": "阴性", "numeric_value": None},
        ]
    )

    aggregated = IndicatorAggregator().aggregate(df)

    row = aggregated.iloc[0]
    assert row["aggregate_summary"] == "阳性"
    assert row["aggregate_detail"] == "HPV16"


def test_aggregate_food_intolerance_non_zero() -> None:
    df = pd.DataFrame(
        [
            {"major_item_standard_name": "食物不耐受", "item_name": "鸡蛋特异性IgG抗体", "text_value": "0级", "numeric_value": None},
            {"major_item_standard_name": "食物不耐受", "item_name": "牛奶特异性IgG抗体", "text_value": "2级", "numeric_value": None},
        ]
    )

    aggregated = IndicatorAggregator().aggregate(df)

    row = aggregated.iloc[0]
    assert row["aggregate_summary"] == "存在不耐受"
    assert row["aggregate_detail"] == "牛奶特异性IgG抗体(2级)"
