from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.pipeline import StandardizationPipeline


class FakeMatcher:
    def is_index_loaded(self) -> bool:
        return True

    def load_index(self, _dir_path: str) -> None:
        return None

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if query not in {"胆固醇偏写"}:
            return []
        if query == "胆固醇偏写":
            return [
                {
                    "standard_code": "HY-BZ-001",
                    "standard_name": "总胆固醇",
                    "category": "血脂",
                    "matched_text": "总胆固醇",
                    "score": 0.91,
                }
            ][:top_k]
        return [
            {
                "standard_code": "HY-BZ-001",
                "standard_name": "总胆固醇",
                "category": "血脂",
                "matched_text": "总胆固醇",
                "score": 0.91,
            }
        ][:top_k]


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
                            "majorItemName": "H-肿瘤标志物",
                            "itemCode": "0401",
                            "itemName": "★甲胎蛋白(AFP)",
                            "itemNameEn": "AFP",
                            "resultValue": "1.74",
                            "unit": "IU/mL",
                            "referenceRange": "",
                            "abnormalFlag": "0",
                        },
                        {
                            "majorItemCode": "101",
                            "majorItemName": "H-血脂",
                            "itemCode": "0402",
                            "itemName": "胆固醇",
                            "itemNameEn": "",
                            "resultValue": "4.5",
                            "unit": "mmol/L",
                            "referenceRange": "",
                            "abnormalFlag": "0",
                        },
                    ],
                }
            ],
        }
    }


def build_pipeline(tmp_path: Path) -> StandardizationPipeline:
    return StandardizationPipeline(
        config_path="config/settings.yaml",
        matcher=FakeMatcher(),
        output_dir=str(tmp_path),
    )


def test_pipeline_json_input(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.json"
    input_path.write_text(json.dumps(sample_json(), ensure_ascii=False), encoding="utf-8")

    classified = build_pipeline(tmp_path).run(str(input_path))

    assert classified["stats"]["total"] == 2
    assert classified["stats"]["auto_count"] == 2


def test_pipeline_csv_input(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.csv"
    pd.DataFrame({"item_name": ["总胆固醇", "胆固醇偏写", "某某新检测项"]}).to_csv(input_path, index=False)

    classified = build_pipeline(tmp_path).run(str(input_path))

    assert classified["stats"]["total"] == 3
    assert classified["stats"]["auto_count"] == 1
    assert classified["stats"]["review_count"] == 1
    assert classified["stats"]["manual_count"] == 1


def test_pipeline_output_files_exist(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.csv"
    pd.DataFrame({"item_name": ["总胆固醇"]}).to_csv(input_path, index=False)

    build_pipeline(tmp_path).run(str(input_path))

    assert (tmp_path / "auto_mapped.csv").exists()
    assert (tmp_path / "need_review.csv").exists()
    assert (tmp_path / "manual_required.csv").exists()
    assert (tmp_path / "stats_report.txt").exists()


def test_pipeline_stats_consistent(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.csv"
    pd.DataFrame({"item_name": ["总胆固醇", "胆固醇偏写", "某某新检测项"]}).to_csv(input_path, index=False)

    stats = build_pipeline(tmp_path).run(str(input_path))["stats"]

    assert stats["total"] == stats["auto_count"] + stats["review_count"] + stats["manual_count"]


def test_pipeline_l1_hit_rate(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.csv"
    pd.DataFrame({"item_name": ["总胆固醇", "胆固醇", "TC", "甲胎蛋白"]}).to_csv(input_path, index=False)

    stats = build_pipeline(tmp_path).run(str(input_path))["stats"]

    assert stats["l1_hit_rate"] >= 0.6


def test_pipeline_auto_mapped_accuracy(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.csv"
    pd.DataFrame({"item_name": ["总胆固醇", "胆固醇", "TC"]}).to_csv(input_path, index=False)

    classified = build_pipeline(tmp_path).run(str(input_path))

    assert {row["standard_code"] for row in classified["auto_mapped"]} == {"HY-BZ-001"}


def test_pipeline_no_data_loss(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.csv"
    pd.DataFrame({"item_name": ["总胆固醇", "胆固醇偏写", "某某新检测项"]}).to_csv(input_path, index=False)

    classified = build_pipeline(tmp_path).run(str(input_path))

    output_count = (
        len(classified["auto_mapped"])
        + len(classified["need_review"])
        + len(classified["manual_required"])
    )
    assert output_count == 3


def test_sample_dirty_has_50_rows() -> None:
    df = pd.read_csv("data/input/sample_dirty.csv")

    assert len(df) == 50


def test_pipeline_sample_dirty_end_to_end(tmp_path: Path) -> None:
    classified = build_pipeline(tmp_path).run("data/input/sample_dirty.csv")
    stats = classified["stats"]

    assert stats["total"] == 50
    assert stats["l1_hit_rate"] >= 0.6
    assert stats["total"] == stats["auto_count"] + stats["review_count"] + stats["manual_count"]
    assert (tmp_path / "auto_mapped.csv").exists()
    assert (tmp_path / "need_review.csv").exists()
    assert (tmp_path / "manual_required.csv").exists()
    assert (tmp_path / "stats_report.txt").exists()


def test_pipeline_sample_dirty_auto_mapped_accuracy(tmp_path: Path) -> None:
    classified = build_pipeline(tmp_path).run("data/input/sample_dirty.csv")

    auto_rows = classified["auto_mapped"][:20]
    assert len(auto_rows) == 20
    assert all(row["standard_code"] for row in auto_rows)
    assert all(row["confidence"] >= 0.95 for row in auto_rows)


def test_pipeline_sample_dirty_no_data_loss(tmp_path: Path) -> None:
    classified = build_pipeline(tmp_path).run("data/input/sample_dirty.csv")

    output_count = (
        len(classified["auto_mapped"])
        + len(classified["need_review"])
        + len(classified["manual_required"])
    )
    assert output_count == 50
