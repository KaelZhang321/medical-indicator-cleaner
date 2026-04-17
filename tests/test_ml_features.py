from __future__ import annotations

import pandas as pd

from scripts.build_ml_features import build_features


def test_build_features() -> None:
    first = pd.DataFrame(
        [{"study_id": "s1", "exam_time": "2024-06-01", "standard_code": "HY-BZ-001", "numeric_value": 4.8, "is_abnormal": False, "category": "血脂"}]
    )
    second = pd.DataFrame(
        [{"study_id": "s2", "exam_time": "2024-12-12", "standard_code": "HY-BZ-001", "numeric_value": 5.65, "is_abnormal": True, "category": "血脂"}]
    )

    features = build_features([first, second])

    assert features.loc[0, "HY-BZ-001_latest"] == 5.65
    assert round(features.loc[0, "HY-BZ-001_change_rate"], 4) == round((5.65 - 4.8) / 4.8, 4)
    assert features.loc[0, "abnormal_count"] == 1
