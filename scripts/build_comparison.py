from __future__ import annotations

import argparse
import pandas as pd
from pathlib import Path
import sys

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)


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
            if first is not None and second is not None:
                if second > first:
                    payload["trend"] = "↑"
                elif second < first:
                    payload["trend"] = "↓"
                else:
                    payload["trend"] = "="
            else:
                payload["trend"] = ""
        else:
            payload["trend"] = ""
        rows.append(payload)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build comparison table from normalized CSV files.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Normalized CSV files.")
    parser.add_argument("--output", required=True, help="Output comparison CSV path.")
    args = parser.parse_args()

    frames = [pd.read_csv(path) for path in args.inputs]
    result = build_comparison_table(frames)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"输出文件: {args.output}")


if __name__ == "__main__":
    main()
