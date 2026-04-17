from __future__ import annotations

import pandas as pd


def build_features(patient_records: list[pd.DataFrame]) -> pd.DataFrame:
    ordered = sorted(patient_records, key=lambda df: df["exam_time"].iloc[0] if not df.empty else "")
    latest = ordered[-1] if ordered else pd.DataFrame()
    previous = ordered[-2] if len(ordered) > 1 else pd.DataFrame()
    features: dict[str, object] = {"abnormal_count": int(latest["is_abnormal"].fillna(False).sum()) if not latest.empty else 0}

    for row in latest.itertuples(index=False):
        features[f"{row.standard_code}_latest"] = row.numeric_value
        if not previous.empty:
            prev_rows = previous.loc[previous["standard_code"] == row.standard_code]
            if not prev_rows.empty and prev_rows.iloc[0]["numeric_value"] not in {None, 0}:
                prev_value = prev_rows.iloc[0]["numeric_value"]
                features[f"{row.standard_code}_change_rate"] = (row.numeric_value - prev_value) / prev_value
    return pd.DataFrame([features])
