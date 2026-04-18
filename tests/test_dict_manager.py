from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.dict_manager import DictManager


def test_load_standard_dict() -> None:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    assert len(manager.standard_dict) >= 150


def test_load_standard_dict_missing_column(tmp_path: Path) -> None:
    standard_path = tmp_path / "standard.csv"
    alias_path = tmp_path / "alias.csv"

    standard_path.write_text(
        "code,standard_name,abbreviation,aliases,category,common_unit\n"
        "040201,总胆固醇,TC,胆固醇;CHOL,血脂,mmol/L\n",
        encoding="utf-8",
    )
    alias_path.write_text(
        "alias,standard_code,source,added_date\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="result_type"):
        DictManager(str(standard_path), str(alias_path))


def test_lookup_by_standard_name() -> None:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    result = manager.lookup("总胆固醇")

    assert result == {
        "standard_code": "040201",
        "standard_name": "总胆固醇",
        "category": "血脂",
    }


def test_lookup_by_alias() -> None:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    result = manager.lookup("CHOL")

    assert result is not None
    assert result["standard_name"] == "总胆固醇"
    assert result["category"] == "血脂"


def test_lookup_by_abbreviation() -> None:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    result = manager.lookup("TC", abbreviation="TC")

    assert result == {
        "standard_code": "040201",
        "standard_name": "总胆固醇",
        "category": "血脂",
    }


def test_lookup_case_insensitive() -> None:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    result = manager.lookup("tc")

    assert result == {
        "standard_code": "040201",
        "standard_name": "总胆固醇",
        "category": "血脂",
    }


def test_lookup_not_found() -> None:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    assert manager.lookup("不存在的名字") is None


def test_add_alias_and_lookup(tmp_path: Path) -> None:
    standard_path = tmp_path / "standard_dict.csv"
    alias_path = tmp_path / "alias_dict.csv"
    pd.read_csv("data/standard_dict.csv").to_csv(standard_path, index=False)
    pd.read_csv("data/alias_dict.csv").to_csv(alias_path, index=False)

    manager = DictManager(str(standard_path), str(alias_path))
    manager.add_alias("总胆固醇项目", "040201")

    result = manager.lookup("总胆固醇项目")

    assert result == {
        "standard_code": "040201",
        "standard_name": "总胆固醇",
        "category": "血脂",
    }


def test_add_alias_no_duplicate(tmp_path: Path) -> None:
    standard_path = tmp_path / "standard_dict.csv"
    alias_path = tmp_path / "alias_dict.csv"
    pd.read_csv("data/standard_dict.csv").to_csv(standard_path, index=False)
    pd.read_csv("data/alias_dict.csv").to_csv(alias_path, index=False)

    manager = DictManager(str(standard_path), str(alias_path))
    manager.add_alias("总胆固醇项目", "040201")
    manager.add_alias("总胆固醇项目", "040201")

    persisted = pd.read_csv(alias_path)
    assert len(persisted[persisted["alias"] == "总胆固醇项目"]) == 1


def test_alias_persisted_to_csv(tmp_path: Path) -> None:
    standard_path = tmp_path / "standard_dict.csv"
    alias_path = tmp_path / "alias_dict.csv"
    pd.read_csv("data/standard_dict.csv").to_csv(standard_path, index=False)
    pd.read_csv("data/alias_dict.csv").to_csv(alias_path, index=False)

    manager = DictManager(str(standard_path), str(alias_path))
    manager.add_alias("总胆固醇项目", "040201", source="manual_review")

    persisted = pd.read_csv(alias_path, dtype=str)
    row = persisted.loc[persisted["alias"] == "总胆固醇项目"].iloc[0]

    assert str(row["standard_code"]) == "040201"
    assert row["source"] == "manual_review"
