from __future__ import annotations

import argparse

import pandas as pd

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from src.dict_manager import DictManager
from src.utils import load_config


REQUIRED_COLUMNS = {"original_name", "standard_code", "confirmed"}


def apply_review_feedback(input_csv: str, config_path: str = "config/settings.yaml") -> dict[str, int]:
    config = load_config(config_path)
    review_df = pd.read_csv(input_csv, dtype=str).fillna("")
    missing = REQUIRED_COLUMNS - set(review_df.columns)
    if missing:
        raise ValueError(f"review feedback missing required columns: {', '.join(sorted(missing))}")

    manager = DictManager(
        config["data"]["standard_dict"],
        config["data"]["alias_dict"],
    )
    confirmed_df = review_df.loc[review_df["confirmed"].astype(str).str.strip() == "1"]

    added = 0
    skipped = 0
    for row in confirmed_df.itertuples(index=False):
        alias = str(row.original_name).strip()
        standard_code = str(row.standard_code).strip()
        before = len(manager.alias_dict)
        manager.add_alias(alias, standard_code, source="manual_review")
        if len(manager.alias_dict) > before:
            added += 1
        else:
            skipped += 1

    return {"confirmed": len(confirmed_df), "added": added, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply reviewed mappings back into alias_dict.csv.")
    parser.add_argument("--input", required=True, help="Confirmed review CSV path.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config file.")
    args = parser.parse_args()

    stats = apply_review_feedback(args.input, args.config)
    print(f"确认行数: {stats['confirmed']}")
    print(f"新增别名: {stats['added']}")
    print(f"跳过重复: {stats['skipped']}")


if __name__ == "__main__":
    main()
