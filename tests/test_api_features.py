from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
import api.routers.analysis as analysis_router


def make_frame(exam_time: str, value: str, abnormal_flag: str) -> pd.DataFrame:
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
                "item_code": "0402",
                "item_name": "胆固醇",
                "item_name_en": "",
                "result_value_raw": value,
                "unit_raw": "mmol/L",
                "reference_range_raw": "0-5.2",
                "abnormal_flag": abnormal_flag,
            }
        ]
    )


class FakePipeline:
    def __init__(self, *args, **kwargs) -> None:
        self.preprocessor = type("FakePreprocessor", (), {"enhance_dataframe": lambda self, frame: frame})()

    def standardize_dataframe(self, dataframe: pd.DataFrame) -> list[dict]:
        standardized = []
        for _, row in dataframe.iterrows():
            numeric = float(row["result_value_raw"])
            standardized.append(
                {
                    **row.to_dict(),
                    "original_name": row["item_name"],
                    "cleaned_name": row["item_name"],
                    "abbreviation": "",
                    "standard_name": "总胆固醇",
                    "standard_code": "040201",
                    "category": "血脂",
                    "standard_unit": "mmol/L",
                    "result_type": "numeric",
                    "confidence": 1.0,
                    "match_source": "alias_exact",
                    "top_candidates": [],
                    "numeric_value": numeric,
                    "ref_min": 0.0,
                    "ref_max": 5.2,
                    "is_abnormal": numeric > 5.2,
                }
            )
        return standardized


def test_features_endpoint_returns_features_for_valid_patient(monkeypatch) -> None:
    monkeypatch.setattr(analysis_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        analysis_router,
        "get_data_source",
        lambda _db: type(
            "DS",
            (),
            {"query_by_patient": lambda self, _sfzh: [make_frame("2025-01-01", "4.8", "0"), make_frame("2025-12-12", "5.65", "2")]},
        )(),
    )
    monkeypatch.setattr(analysis_router, "StandardizationPipeline", FakePipeline)

    client = TestClient(app)
    response = client.get("/api/v1/patient/123456789012345678/features")

    assert response.status_code == 200
    body = response.json()
    assert body["exam_count"] == 2
    assert body["summary"]["abnormal_count"] == 1
    assert body["features"]["040201_latest"] == 5.65
    assert round(body["features"]["040201_change_rate"], 4) == 0.1771
    assert body["indicators"][0]["code"] == "040201"


def test_features_endpoint_filters_old_data(monkeypatch) -> None:
    monkeypatch.setattr(analysis_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        analysis_router,
        "get_data_source",
        lambda _db: type("DS", (), {"query_by_patient": lambda self, _sfzh: [make_frame("2020-01-01", "4.8", "0")]})(),
    )
    monkeypatch.setattr(analysis_router, "StandardizationPipeline", FakePipeline)

    client = TestClient(app)
    response = client.get("/api/v1/patient/123456789012345678/features")

    assert response.status_code == 404
    assert response.json()["detail"] == "近三年内无体检数据"
