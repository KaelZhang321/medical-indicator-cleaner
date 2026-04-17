from __future__ import annotations

import pandas as pd

from scripts.build_comparison import build_comparison_table


def test_build_comparison_table() -> None:
    first = pd.DataFrame(
        [{"study_id": "s1", "exam_time": "2024-06-01", "standard_code": "HY-BZ-001", "standard_name": "总胆固醇", "category": "血脂", "numeric_value": 4.8}]
    )
    second = pd.DataFrame(
        [{"study_id": "s2", "exam_time": "2024-12-12", "standard_code": "HY-BZ-001", "standard_name": "总胆固醇", "category": "血脂", "numeric_value": 5.65}]
    )

    table = build_comparison_table([first, second])

    assert table.loc[0, "2024-06-01"] == 4.8
    assert table.loc[0, "2024-12-12"] == 5.65
    assert table.loc[0, "trend"] == "↑"


def test_build_comparison_table_ignores_none_for_trend() -> None:
    first = pd.DataFrame(
        [{"study_id": "s1", "exam_time": "2024-06-01", "standard_code": "HY-BZ-001", "standard_name": "总胆固醇", "category": "血脂", "numeric_value": None}]
    )
    second = pd.DataFrame(
        [{"study_id": "s2", "exam_time": "2024-12-12", "standard_code": "HY-BZ-001", "standard_name": "总胆固醇", "category": "血脂", "numeric_value": 5.65}]
    )

    table = build_comparison_table([first, second])

    assert table.loc[0, "trend"] == ""
