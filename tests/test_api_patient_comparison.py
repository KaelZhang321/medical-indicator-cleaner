from __future__ import annotations

import pandas as pd
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.main import app
import api.routers.patient as patient_router


def make_numeric_frame(exam_time: str, value: str, abnormal_flag: str = "0") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": f"study-{exam_time}",
                "exam_time": exam_time,
                "package_name": "示例套餐",
                "patient_name": "张三",
                "gender": "男",
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


def make_text_frame(exam_time: str, text_value: str, *, item_name: str = "甲状腺超声提示") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": f"study-{exam_time}",
                "exam_time": exam_time,
                "package_name": "示例套餐",
                "patient_name": "张三",
                "gender": "女",
                "dept_code": "FK",
                "dept_name": "妇科",
                "source_table": "ods_tj_fkb",
                "major_item_code": "2701",
                "major_item_name": "甲状腺超声",
                "item_code": "270118",
                "item_name": item_name,
                "item_name_en": "",
                "result_value_raw": text_value,
                "unit_raw": "",
                "reference_range_raw": "",
                "abnormal_flag": None,
            }
        ]
    )


def make_plain_text_frame(exam_time: str, text_value: str, *, item_name: str = "心率") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": f"study-{exam_time}",
                "exam_time": exam_time,
                "package_name": "示例套餐",
                "patient_name": "张三",
                "gender": "女",
                "dept_code": "NK",
                "dept_name": "内科",
                "source_table": "ods_tj_nkb",
                "major_item_code": "",
                "major_item_name": "",
                "item_code": "900001",
                "item_name": item_name,
                "item_name_en": "",
                "result_value_raw": text_value,
                "unit_raw": "",
                "reference_range_raw": "",
                "abnormal_flag": None,
            }
        ]
    )


class FakeCleaner:
    def clean(self, item_name: str):
        if "超声" in item_name or "结论" in item_name:
            return type(
                "CleanResult",
                (),
                {
                    "standard_code": "270118",
                    "standard_name": "甲状腺超声提示",
                    "cleaned": "甲状腺超声提示",
                    "category": "影像/结论",
                },
            )()
        return type(
            "CleanResult",
            (),
            {
                "standard_code": "040201",
                "standard_name": "总胆固醇",
                "cleaned": "总胆固醇",
                "category": "血脂",
            },
        )()


def test_comparison_endpoint_returns_numeric_mode_by_default(monkeypatch) -> None:
    monkeypatch.setattr(patient_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        patient_router,
        "get_data_source",
        lambda _db: type(
            "DS",
            (),
            {
                "query_by_patient": lambda self, _sfzh: [
                    make_numeric_frame("2025-01-01", "4.8", "0"),
                    make_numeric_frame("2025-12-12", "5.6", "2"),
                ]
            },
        )(),
    )
    monkeypatch.setattr(patient_router, "get_cleaner", lambda: FakeCleaner())
    monkeypatch.setattr(
        patient_router,
        "get_reference_ranges",
        lambda: pd.DataFrame([{"standard_code": "040201", "ref_min": 0.0, "ref_max": 5.2}]),
    )

    client = TestClient(app)
    response = client.get("/api/v1/patient/123456789012345678/comparison")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "numeric"
    assert body["exam_dates"] == ["2025-01-01", "2025-12-12"]
    assert body["comparisons"][0]["standard_code"] == "040201"
    assert body["comparisons"][0]["values"]["2025-12-12"] == 5.6
    assert body["comparisons"][0]["trend"] == "↑"


def test_comparison_endpoint_returns_text_mode_for_imaging_and_conclusion(monkeypatch) -> None:
    monkeypatch.setattr(patient_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        patient_router,
        "get_data_source",
        lambda _db: type(
            "DS",
            (),
            {
                "query_by_patient": lambda self, _sfzh: [
                    make_text_frame("2024-01-01", "左叶结节，建议复查"),
                    make_text_frame("2025-01-01", "左叶结节，较前相仿"),
                ]
            },
        )(),
    )
    monkeypatch.setattr(patient_router, "get_cleaner", lambda: FakeCleaner())
    monkeypatch.setattr(patient_router, "get_reference_ranges", lambda: pd.DataFrame())

    client = TestClient(app)
    response = client.get("/api/v1/patient/123456789012345678/comparison", params={"mode": "text"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "text"
    assert body["exam_dates"] == ["2024-01-01", "2025-01-01"]
    assert body["comparisons"][0]["standard_code"] == "270118"
    assert body["comparisons"][0]["unit"] == ""
    assert body["comparisons"][0]["values"]["2024-01-01"] == "左叶结节，建议复查"
    assert body["comparisons"][0]["values"]["2025-01-01"] == "左叶结节，较前相仿"
    assert body["comparisons"][0]["trend"] == "变化"


def test_comparison_text_mode_can_filter_category(monkeypatch) -> None:
    monkeypatch.setattr(patient_router, "get_db", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        patient_router,
        "get_data_source",
        lambda _db: type(
            "DS",
            (),
            {
                "query_by_patient": lambda self, _sfzh: [
                    make_text_frame("2024-01-01", "甲状腺结节"),
                    make_text_frame("2025-01-01", "甲状腺结节"),
                ]
            },
        )(),
    )
    monkeypatch.setattr(patient_router, "get_cleaner", lambda: FakeCleaner())
    monkeypatch.setattr(patient_router, "get_reference_ranges", lambda: pd.DataFrame())

    client = TestClient(app)
    response = client.get(
        "/api/v1/patient/123456789012345678/comparison",
        params={"mode": "text", "category": "影像/结论"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["comparisons"]) == 1
    assert body["comparisons"][0]["category"] == "影像/结论"
