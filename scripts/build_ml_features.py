from __future__ import annotations

import argparse
import math

import pandas as pd
from pathlib import Path
import sys

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)


def build_features(patient_records: list[pd.DataFrame]) -> pd.DataFrame:
    ordered = sorted(
        patient_records,
        key=lambda df: str(df["exam_time"].iloc[0])[:10] if not df.empty else "",
    )
    latest = ordered[-1] if ordered else pd.DataFrame()
    previous = ordered[-2] if len(ordered) > 1 else pd.DataFrame()
    features: dict[str, object] = {"abnormal_count": int(latest["is_abnormal"].fillna(False).sum()) if not latest.empty else 0}

    for row in latest.itertuples(index=False):
        features[f"{row.standard_code}_latest"] = row.numeric_value
        if not previous.empty:
            prev_rows = previous.loc[previous["standard_code"] == row.standard_code]
            if not prev_rows.empty:
                cur = row.numeric_value
                prev = prev_rows.iloc[0]["numeric_value"]
                if (
                    cur is not None
                    and prev is not None
                    and not pd.isna(cur)
                    and not pd.isna(prev)
                    and not (isinstance(prev, float) and math.isnan(prev))
                    and prev != 0
                ):
                    features[f"{row.standard_code}_change_rate"] = (cur - prev) / prev
    return pd.DataFrame([features])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ML feature table from normalized CSV files.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Normalized CSV files in chronological order.")
    parser.add_argument("--output", required=True, help="Output features CSV path.")
    args = parser.parse_args()

    frames = [pd.read_csv(path) for path in args.inputs]
    result = build_features(frames)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"输出文件: {args.output}")


if __name__ == "__main__":
    main()
