from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p0_preprocessor import P0Preprocessor
from src.utils import load_config


REAL_SAMPLE_PATH = Path("lxl-2512125012.txt")


@pytest.fixture
def config() -> dict:
    return load_config("config/settings.yaml")


@pytest.fixture
def preprocessor(config: dict) -> P0Preprocessor:
    return P0Preprocessor(config)


@pytest.fixture
def sample_json() -> dict:
    return {
        "data": {
            "studyId": "study-001",
            "examTime": "2025-12-12 08:01:20",
            "packageName": "示例套餐",
            "departments": [
                {
                    "departmentCode": "HY",
                    "departmentName": "化验室",
                    "sourceTable": "ods_tj_hyb",
                    "items": [
                        {
                            "majorItemCode": "100",
                            "majorItemName": "H-免疫检测",
                            "itemCode": "0401",
                            "itemName": "人类免疫缺陷病毒抗体(HIV-Ab)",
                            "itemNameEn": "HIV-Ab",
                            "resultValue": "0.07（阴性 -）",
                            "unit": "S/CO",
                            "referenceRange": "",
                            "abnormalFlag": "0",
                        },
                        {
                            "majorItemCode": "100",
                            "majorItemName": "H-免疫检测",
                            "itemCode": "0401",
                            "itemName": "人类免疫缺陷病毒抗体(HIV-Ab)",
                            "itemNameEn": "HIV-Ab",
                            "resultValue": "0.09（阴性 -）",
                            "unit": "S/CO",
                            "referenceRange": "",
                            "abnormalFlag": "0",
                        },
                    ],
                },
                {
                    "departmentCode": "ER",
                    "departmentName": "人体成分",
                    "sourceTable": "ods_tj_erb",
                    "items": [
                        {
                            "majorItemCode": "200",
                            "majorItemName": "H-人体成分",
                            "itemCode": "0501",
                            "itemName": "身体总水分",
                            "itemNameEn": "TBW",
                            "resultValue": "28.2kg",
                            "unit": "",
                            "referenceRange": "",
                            "abnormalFlag": None,
                        }
                    ],
                },
                {
                    "departmentCode": "YB",
                    "departmentName": "一般检查",
                    "sourceTable": "ods_tj_ybb",
                    "items": [
                        {
                            "majorItemCode": "300",
                            "majorItemName": "一般检查",
                            "itemCode": "0601",
                            "itemName": "收缩压",
                            "itemNameEn": "SBP",
                            "resultValue": "124",
                            "unit": "mmHg",
                            "referenceRange": "",
                            "abnormalFlag": "0",
                        }
                    ],
                },
                {
                    "departmentCode": "WZ",
                    "departmentName": "健康问诊",
                    "sourceTable": "ods_tj_wzb",
                    "items": [
                        {
                            "majorItemCode": "400",
                            "majorItemName": "问诊",
                            "itemCode": "0701",
                            "itemName": "胃胀/胃疼/嗳气/反酸",
                            "itemNameEn": "",
                            "resultValue": "1",
                            "unit": "",
                            "referenceRange": "",
                            "abnormalFlag": None,
                        }
                    ],
                },
            ],
        }
    }


def test_flatten_items_column_names(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor._flatten_items(sample_json)

    assert list(df.columns) == [
        "study_id",
        "exam_time",
        "package_name",
        "dept_code",
        "dept_name",
        "source_table",
        "major_item_code",
        "major_item_name",
        "item_code",
        "item_name",
        "item_name_en",
        "result_value_raw",
        "unit_raw",
        "reference_range_raw",
        "abnormal_flag",
    ]


def test_filter_departments_whitelist(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor._flatten_items(sample_json)
    filtered = preprocessor._filter_departments(df)

    assert set(filtered["dept_code"].unique()) == {"HY", "ER", "YB"}


def test_filter_departments_removes_wz(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor._flatten_items(sample_json)
    filtered = preprocessor._filter_departments(df)

    assert "WZ" not in filtered["dept_code"].values


def test_deduplicate_removes_dupes(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor._flatten_items(sample_json)
    filtered = preprocessor._filter_departments(df)
    deduplicated = preprocessor._deduplicate(filtered)

    assert len(filtered) == 4
    assert len(deduplicated) == 3


def test_deduplicate_keeps_first(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor._flatten_items(sample_json)
    filtered = preprocessor._filter_departments(df)
    deduplicated = preprocessor._deduplicate(filtered)

    hiv_row = deduplicated.loc[deduplicated["item_code"] == "0401"].iloc[0]
    assert hiv_row["result_value_raw"] == "0.07（阴性 -）"


def test_process_end_to_end(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor.process(sample_json)

    assert len(df) == 3
    assert {
        "numeric_value",
        "text_value",
        "unit_parsed",
        "qualifier",
        "judgment",
        "ref_in_value",
        "unit",
    }.issubset(df.columns)


def test_process_er_unit_parsed(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor.process(sample_json)

    er_row = df.loc[df["dept_code"] == "ER"].iloc[0]
    assert er_row["unit"] == "kg"
    assert er_row["unit_parsed"] == "kg"
    assert er_row["numeric_value"] == 28.2


def test_process_hy_unit_preserved(preprocessor: P0Preprocessor, sample_json: dict) -> None:
    df = preprocessor.process(sample_json)

    hy_row = df.loc[df["dept_code"] == "HY"].iloc[0]
    assert hy_row["unit_raw"] == "S/CO"
    assert hy_row["unit"] == "S/CO"
    assert hy_row["numeric_value"] == 0.07


def test_process_batch_multiple_files(preprocessor: P0Preprocessor, sample_json: dict, tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(sample_json, ensure_ascii=False), encoding="utf-8")
    second.write_text(json.dumps(sample_json, ensure_ascii=False), encoding="utf-8")

    df = preprocessor.process_batch([str(first), str(second)])

    assert len(df) == 6


@pytest.mark.skipif(not REAL_SAMPLE_PATH.exists(), reason="real sample file not available")
def test_flatten_items_real_sample_row_count(preprocessor: P0Preprocessor) -> None:
    data = json.loads(REAL_SAMPLE_PATH.read_text(encoding="utf-8"))

    df = preprocessor._flatten_items(data)

    assert len(df) == 504


@pytest.mark.skipif(not REAL_SAMPLE_PATH.exists(), reason="real sample file not available")
def test_filter_departments_real_sample_count(preprocessor: P0Preprocessor) -> None:
    data = json.loads(REAL_SAMPLE_PATH.read_text(encoding="utf-8"))

    df = preprocessor._flatten_items(data)
    filtered = preprocessor._filter_departments(df)

    assert len(filtered) == 142
    assert filtered["dept_code"].value_counts().to_dict() == {"HY": 107, "ER": 26, "YB": 9}
