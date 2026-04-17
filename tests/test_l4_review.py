from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.l4_review import L4Review


def record(name: str, confidence: float, match_source: str = "l2_embedding") -> dict:
    return {
        "original_name": name,
        "cleaned_name": name,
        "abbreviation": "",
        "standard_name": "总胆固醇" if confidence >= 0.8 else "",
        "standard_code": "HY-BZ-001" if confidence >= 0.8 else "",
        "category": "血脂" if confidence >= 0.8 else "",
        "confidence": confidence,
        "match_source": match_source,
        "top_candidates": [
            {"standard_name": "总胆固醇", "standard_code": "HY-BZ-001", "score": confidence},
            {"standard_name": "甘油三酯", "standard_code": "HY-BZ-002", "score": 0.77},
            {"standard_name": "高密度脂蛋白胆固醇", "standard_code": "HY-BZ-003", "score": 0.66},
            {"standard_name": "低密度脂蛋白胆固醇", "standard_code": "HY-BZ-004", "score": 0.55},
        ],
    }


def test_classify_auto_mapped() -> None:
    classified = L4Review().classify([record("总胆固醇", 1.0, "alias_exact")])

    assert len(classified["auto_mapped"]) == 1
    assert classified["stats"]["auto_count"] == 1


def test_classify_need_review() -> None:
    classified = L4Review().classify([record("胆固醇", 0.9)])

    assert len(classified["need_review"]) == 1
    assert classified["stats"]["review_count"] == 1


def test_classify_manual_required() -> None:
    classified = L4Review().classify([record("某某新检测项", 0.7)])

    assert len(classified["manual_required"]) == 1
    assert classified["stats"]["manual_count"] == 1


def test_classify_boundary_095() -> None:
    classified = L4Review().classify([record("边界自动", 0.95)])

    assert len(classified["auto_mapped"]) == 1


def test_classify_boundary_080() -> None:
    classified = L4Review().classify([record("边界审核", 0.80)])

    assert len(classified["need_review"]) == 1


def test_classify_stats_sum() -> None:
    classified = L4Review().classify(
        [
            record("自动", 1.0, "alias_exact"),
            record("审核", 0.9),
            record("人工", 0.7),
        ]
    )

    stats = classified["stats"]
    assert stats["auto_count"] + stats["review_count"] + stats["manual_count"] == stats["total"]
    assert stats["l1_hit_count"] == 1
    assert stats["l1_hit_rate"] == 1 / 3


def test_export_csv_files_created(tmp_path: Path) -> None:
    classified = L4Review().classify([record("自动", 1.0), record("审核", 0.9), record("人工", 0.7)])

    L4Review().export_csv(classified, str(tmp_path))

    assert (tmp_path / "auto_mapped.csv").exists()
    assert (tmp_path / "need_review.csv").exists()
    assert (tmp_path / "manual_required.csv").exists()
    assert (tmp_path / "stats_report.txt").exists()


def test_export_csv_utf8_bom(tmp_path: Path) -> None:
    classified = L4Review().classify([record("自动", 1.0)])

    L4Review().export_csv(classified, str(tmp_path))

    assert (tmp_path / "auto_mapped.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_export_csv_candidates_column(tmp_path: Path) -> None:
    classified = L4Review().classify([record("审核", 0.9)])

    L4Review().export_csv(classified, str(tmp_path))

    df = pd.read_csv(tmp_path / "need_review.csv")
    assert "top3_candidates" in df.columns
    candidates = json.loads(df.loc[0, "top3_candidates"])
    assert len(candidates) == 3
    assert candidates[0]["standard_name"] == "总胆固醇"
