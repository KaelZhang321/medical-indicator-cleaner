from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
import api.routers.analysis as analysis_router


def make_db_frame(exam_time: str, value: str, abnormal_flag: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "s1",
                "exam_time": exam_time,
                "package_name": "示例套餐",
                "dept_code": "HY",
                "dept_name": "化验室",
                "source_table": "ods_tj_hyb",
                "major_item_code": "100",
                "major_item_name": "H-血脂",
                "item_code": "040201",
                "item_name": "总胆固醇(TC)",
                "item_name_en": "TC",
                "result_value_raw": value,
                "unit_raw": "mmol/L",
                "reference_range_raw": "0-5.2",
                "abnormal_flag": abnormal_flag,
            }
        ]
    )


def test_features_endpoint_uses_standardized_fields(monkeypatch) -> None:
    monkeypatch.setattr(analysis_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        analysis_router,
        "get_data_source",
        lambda _db: type("DS", (), {"query_by_patient": lambda self, _sfzh: [make_db_frame("2025-01-01", "4.8", "0"), make_db_frame("2025-12-12", "5.65", "2")]})(),
    )

    client = TestClient(app)
    response = client.get("/api/v1/patient/123456789012345678/features")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["abnormal_count"] >= 0
    assert body["exam_count"] == 2
    assert body["overall_score"] > 0
    assert len(body["indicators"]) > 0
    assert body["indicators"][0]["code"] != ""


def test_features_endpoint_sanitizes_nan_values(monkeypatch) -> None:
    monkeypatch.setattr(analysis_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        analysis_router,
        "get_data_source",
        lambda _db: type("DS", (), {"query_by_patient": lambda self, _sfzh: [make_db_frame("2025-01-01", "4.8", "0"), make_db_frame("2025-12-12", "5.65", "2")]})(),
    )

    client = TestClient(app)
    response = client.get("/api/v1/patient/123456789012345678/features")

    assert response.status_code == 200
    body = response.json()
    # Verify no NaN values in JSON (NaN is not valid JSON)
    import json
    raw = response.text
    assert "NaN" not in raw
    assert body["overall_score"] <= 100
