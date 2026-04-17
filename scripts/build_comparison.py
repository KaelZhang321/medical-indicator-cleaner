from __future__ import annotations

import pandas as pd


def build_comparison_table(results: list[pd.DataFrame]) -> pd.DataFrame:
    merged: dict[tuple[str, str, str], dict[str, object]] = {}
    for dataframe in results:
        for row in dataframe.itertuples(index=False):
            key = (row.standard_code, row.standard_name, row.category)
            merged.setdefault(
                key,
                {
                    "standard_code": row.standard_code,
                    "standard_name": row.standard_name,
                    "category": row.category,
                },
            )
            merged[key][str(row.exam_time)[:10]] = row.numeric_value

    rows = []
    for payload in merged.values():
        dates = sorted(key for key in payload.keys() if key[:4].isdigit())
        if len(dates) >= 2:
            first, second = payload[dates[-2]], payload[dates[-1]]
            if second > first:
                payload["trend"] = "↑"
            elif second < first:
                payload["trend"] = "↓"
            else:
                payload["trend"] = "="
        else:
            payload["trend"] = ""
        rows.append(payload)
    return pd.DataFrame(rows)
