from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from scripts.review_feedback import apply_review_feedback
from src.dict_manager import DictManager


def write_test_config(tmp_path: Path) -> Path:
    standard_path = tmp_path / "standard_dict.csv"
    alias_path = tmp_path / "alias_dict.csv"
    pd.read_csv("data/standard_dict.csv").to_csv(standard_path, index=False)
    pd.read_csv("data/alias_dict.csv").to_csv(alias_path, index=False)

    config = {
        "data": {
            "standard_dict": str(standard_path),
            "alias_dict": str(alias_path),
            "input_dir": "./data/input",
            "output_dir": str(tmp_path / "output"),
        },
        "model": {"name": "fake", "cache_dir": "./models", "device": "cpu"},
        "index": {"path": str(tmp_path / "index"), "top_k": 5},
        "thresholds": {"auto_map": 0.95, "need_review": 0.80},
        "departments": {"whitelist": ["HY", "YB", "ER"], "blacklist": ["WZ", "EY", "EZ"]},
        "preprocessing": {"deduplicate": True, "parse_result_value": True},
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return config_path


def read_config(config_path: Path) -> dict:
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def test_review_feedback_adds_confirmed_alias(tmp_path: Path) -> None:
    config_path = write_test_config(tmp_path)
    review_path = tmp_path / "confirmed.csv"
    pd.DataFrame(
        [
            {"original_name": "胆固醇偏写", "standard_code": "HY-BZ-001", "confirmed": 1},
            {"original_name": "拒绝项", "standard_code": "HY-BZ-001", "confirmed": 0},
        ]
    ).to_csv(review_path, index=False)

    stats = apply_review_feedback(str(review_path), str(config_path))

    assert stats == {"confirmed": 1, "added": 1, "skipped": 0}
    config = read_config(config_path)
    manager = DictManager(config["data"]["standard_dict"], config["data"]["alias_dict"])
    assert manager.lookup("胆固醇偏写")["standard_code"] == "HY-BZ-001"
    assert manager.lookup("拒绝项") is None


def test_review_feedback_skips_duplicates(tmp_path: Path) -> None:
    config_path = write_test_config(tmp_path)
    review_path = tmp_path / "confirmed.csv"
    pd.DataFrame(
        [
            {"original_name": "胆固醇偏写", "standard_code": "HY-BZ-001", "confirmed": 1},
            {"original_name": "胆固醇偏写", "standard_code": "HY-BZ-001", "confirmed": 1},
        ]
    ).to_csv(review_path, index=False)

    stats = apply_review_feedback(str(review_path), str(config_path))

    assert stats == {"confirmed": 2, "added": 1, "skipped": 1}


def test_review_feedback_requires_columns(tmp_path: Path) -> None:
    config_path = write_test_config(tmp_path)
    review_path = tmp_path / "bad.csv"
    pd.DataFrame([{"original_name": "胆固醇偏写"}]).to_csv(review_path, index=False)

    try:
        apply_review_feedback(str(review_path), str(config_path))
    except ValueError as exc:
        assert "standard_code" in str(exc)
        assert "confirmed" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing columns")


def test_review_feedback_alias_file_has_new_row(tmp_path: Path) -> None:
    config_path = write_test_config(tmp_path)
    review_path = tmp_path / "confirmed.csv"
    pd.DataFrame(
        [{"original_name": "胆固醇偏写", "standard_code": "HY-BZ-001", "confirmed": 1}]
    ).to_csv(review_path, index=False)

    apply_review_feedback(str(review_path), str(config_path))

    config = read_config(config_path)
    alias_df = pd.read_csv(config["data"]["alias_dict"])
    row = alias_df.loc[alias_df["alias"] == "胆固醇偏写"].iloc[0]
    assert row["standard_code"] == "HY-BZ-001"
    assert row["source"] == "manual_review"
