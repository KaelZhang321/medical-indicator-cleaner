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
            elif rule["method"] == "leukorrhea_summary":
                fungus = group.loc[group["item_name"] == "霉菌", "text_value"].iloc[0] if not group.loc[group["item_name"] == "霉菌"].empty else ""
                trich = group.loc[group["item_name"] == "滴虫", "text_value"].iloc[0] if not group.loc[group["item_name"] == "滴虫"].empty else ""
                clean = group.loc[group["item_name"] == "清洁度", "text_value"].iloc[0] if not group.loc[group["item_name"] == "清洁度"].empty else ""
                rows.append(
                    {
                        "major_item_standard_name": major_item_name,
                        "aggregate_summary": "阴性" if fungus == "阴性" and trich == "阴性" else "异常",
                        "aggregate_detail": f"清洁度({clean})" if clean else "",
                    }
                )
            elif rule["method"] == "blood_type_combo":
                abo = group.loc[group["item_name"] == "ABO血型", "text_value"].iloc[0] if not group.loc[group["item_name"] == "ABO血型"].empty else ""
                rh = group.loc[group["item_name"].astype(str).str.contains("RH"), "text_value"].iloc[0] if not group.loc[group["item_name"].astype(str).str.contains("RH")].empty else ""
                rows.append(
                    {
                        "major_item_standard_name": major_item_name,
                        "aggregate_summary": f"{abo} RH{rh}",
                        "aggregate_detail": f"ABO({abo}), RH({rh})",
                    }
                )
        return pd.DataFrame(rows)
