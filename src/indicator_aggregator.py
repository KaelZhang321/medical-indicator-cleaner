from __future__ import annotations

import yaml
import pandas as pd


class IndicatorAggregator:
    """Aggregate bulky indicator groups like HPV and food intolerance."""

    def __init__(self, rules_path: str = "data/aggregate_rules.yaml") -> None:
        with open(rules_path, "r", encoding="utf-8") as file:
            self.rules = yaml.safe_load(file) or {}

    def aggregate(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for major_item_name, group in dataframe.groupby("major_item_standard_name"):
            rule = self.rules.get(major_item_name)
            if not rule:
                continue
            if rule["method"] == "any_positive":
                positive_rows = group[group["text_value"].fillna("").astype(str).str.contains("阳性")]
                rows.append(
                    {
                        "major_item_standard_name": major_item_name,
                        "aggregate_summary": "阳性" if not positive_rows.empty else "阴性",
                        "aggregate_detail": ",".join(positive_rows["item_name"].tolist()),
                    }
                )
            elif rule["method"] == "non_zero_list":
                non_zero = group[group["text_value"].fillna("").astype(str) != "0级"]
                rows.append(
                    {
                        "major_item_standard_name": major_item_name,
                        "aggregate_summary": "存在不耐受" if not non_zero.empty else "全部0级",
                        "aggregate_detail": ",".join(
                            f"{row.item_name}({row.text_value})" for row in non_zero.itertuples(index=False)
                        ),
                    }
                )
        return pd.DataFrame(rows)
