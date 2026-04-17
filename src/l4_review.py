from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils import ensure_dir


BASE_COLUMNS = [
    "original_name",
    "cleaned_name",
    "abbreviation",
    "standard_name",
    "standard_code",
    "category",
    "confidence",
    "match_source",
]


class L4Review:
    """Classify normalization results into output review buckets."""

    def __init__(self, auto_threshold: float = 0.95, review_threshold: float = 0.80) -> None:
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    def classify(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        auto_mapped: list[dict[str, Any]] = []
        need_review: list[dict[str, Any]] = []
        manual_required: list[dict[str, Any]] = []

        for result in results:
            confidence = float(result.get("confidence") or 0.0)
            if confidence >= self.auto_threshold:
                auto_mapped.append(result)
            elif confidence >= self.review_threshold:
                need_review.append(result)
            else:
                manual_required.append(result)

        total = len(results)
        l1_hit_count = sum(1 for result in results if str(result.get("match_source", "")).endswith("_exact"))
        stats = {
            "total": total,
            "auto_count": len(auto_mapped),
            "review_count": len(need_review),
            "manual_count": len(manual_required),
            "l1_hit_count": l1_hit_count,
            "l1_hit_rate": l1_hit_count / total if total else 0.0,
        }
        return {
            "auto_mapped": auto_mapped,
            "need_review": need_review,
            "manual_required": manual_required,
            "stats": stats,
        }

    def export_csv(self, classified: dict[str, Any], output_dir: str) -> None:
        target = Path(output_dir)
        ensure_dir(target)

        self._write_csv(classified["auto_mapped"], target / "auto_mapped.csv", BASE_COLUMNS)
        self._write_csv(
            self._with_candidates(classified["need_review"], "top3_candidates", 3),
            target / "need_review.csv",
            BASE_COLUMNS + ["top3_candidates"],
        )
        self._write_csv(
            self._with_candidates(classified["manual_required"], "top5_candidates", 5),
            target / "manual_required.csv",
            BASE_COLUMNS + ["top5_candidates"],
        )
        (target / "stats_report.txt").write_text(
            self._format_stats_report(classified["stats"]),
            encoding="utf-8",
        )

    def _write_csv(self, rows: list[dict[str, Any]], path: Path, columns: list[str]) -> None:
        normalized_rows = [{column: row.get(column, "") for column in columns} for row in rows]
        pd.DataFrame(normalized_rows, columns=columns).to_csv(path, index=False, encoding="utf-8-sig")

    def _with_candidates(self, rows: list[dict[str, Any]], column_name: str, limit: int) -> list[dict[str, Any]]:
        exported: list[dict[str, Any]] = []
        for row in rows:
            copied = dict(row)
            copied[column_name] = json.dumps(
                copied.get("top_candidates", [])[:limit],
                ensure_ascii=False,
            )
            exported.append(copied)
        return exported

    def _format_stats_report(self, stats: dict[str, Any]) -> str:
        total = int(stats.get("total", 0))

        def ratio(count: int) -> float:
            return count / total if total else 0.0

        auto_count = int(stats.get("auto_count", 0))
        review_count = int(stats.get("review_count", 0))
        manual_count = int(stats.get("manual_count", 0))
        l1_hit_count = int(stats.get("l1_hit_count", 0))
        return "\n".join(
            [
                "========= 标准化统计报告 =========",
                f"总指标数:        {total}",
                f"自动归一:        {auto_count} ({ratio(auto_count):.1%})",
                f"待人工审核:      {review_count} ({ratio(review_count):.1%})",
                f"需人工处理:      {manual_count} ({ratio(manual_count):.1%})",
                f"L1 命中数:       {l1_hit_count} ({float(stats.get('l1_hit_rate', 0.0)):.1%})",
                "=================================",
                "",
            ]
        )
