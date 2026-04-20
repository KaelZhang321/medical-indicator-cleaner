from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db_data_source import DBDataSource


class FakeDB:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute_query(self, sql: str, params: tuple | None = None) -> pd.DataFrame:
        self.queries.append(sql)
        compact_sql = " ".join(sql.split())

        if compact_sql.startswith("SHOW COLUMNS FROM `ods_tj_usb`"):
            return pd.DataFrame([{"Field": "StudyID"}, {"Field": "XXDM"}, {"Field": "ItemResult"}])

        if compact_sql.startswith("SHOW COLUMNS FROM `ods_tj_jlb`"):
            return pd.DataFrame([{"Field": "StudyID"}, {"Field": "JCJG"}, {"Field": "ZJJL"}])

        if "FROM ods_tj_hyb h" in compact_sql:
            return pd.DataFrame()

        if "FROM `ods_tj_ybb` d" in compact_sql or "FROM `ods_tj_erb` d" in compact_sql or "FROM `ods_tj_nkb` d" in compact_sql or "FROM `ods_tj_wkb` d" in compact_sql or "FROM `ods_tj_fkb` d" in compact_sql:
            return pd.DataFrame()

        if "FROM `ods_tj_usb` d" in compact_sql:
            assert "d.ItemResult as result_value_raw" in compact_sql
            return pd.DataFrame(
                [
                    {
                        "study_id": "study-1",
                        "exam_time": "2025-01-01",
                        "patient_name": "张三",
                        "gender": "女",
                        "birth_date": "1973-10-20",
                        "package_name": "示例套餐",
                        "dept_code": "US",
                        "dept_name": "彩超室",
                        "source_table": "ods_tj_usb",
                        "major_item_code": "",
                        "major_item_name": "",
                        "item_code": "000003",
                        "item_name": "检查所见",
                        "item_name_en": "US PACS 结论",
                        "result_value_raw": "甲状腺结节",
                        "unit_raw": "",
                        "reference_range_raw": "",
                        "abnormal_flag": None,
                    }
                ]
            )

        if "UNION ALL" in compact_sql and "FROM `ods_tj_jlb` d" in compact_sql:
            assert "'JCJG' as item_code" in compact_sql
            assert "'ZJJL' as item_code" in compact_sql
            return pd.DataFrame(
                [
                    {
                        "study_id": "study-1",
                        "exam_time": "2025-01-01",
                        "patient_name": "张三",
                        "gender": "女",
                        "birth_date": "1973-10-20",
                        "package_name": "示例套餐",
                        "dept_code": "JL",
                        "dept_name": "总检室",
                        "source_table": "ods_tj_jlb",
                        "major_item_code": "",
                        "major_item_name": "",
                        "item_code": "JCJG",
                        "item_name": "异常结果汇总",
                        "item_name_en": "JCJG",
                        "result_value_raw": "血压偏高",
                        "unit_raw": "",
                        "reference_range_raw": "",
                        "abnormal_flag": None,
                    },
                    {
                        "study_id": "study-1",
                        "exam_time": "2025-01-01",
                        "patient_name": "张三",
                        "gender": "女",
                        "birth_date": "1973-10-20",
                        "package_name": "示例套餐",
                        "dept_code": "JL",
                        "dept_name": "总检室",
                        "source_table": "ods_tj_jlb",
                        "major_item_code": "",
                        "major_item_name": "",
                        "item_code": "ZJJL",
                        "item_name": "总检结论",
                        "item_name_en": "ZJJL",
                        "result_value_raw": "建议复查甲状腺超声",
                        "unit_raw": "",
                        "reference_range_raw": "",
                        "abnormal_flag": None,
                    },
                ]
            )

        raise AssertionError(f"Unexpected SQL: {compact_sql}")


def test_query_by_study_id_detects_usb_and_jlb_text_columns() -> None:
    ds = DBDataSource(FakeDB())

    result = ds.query_by_study_id("study-1")

    assert not result.empty
    assert set(result["source_table"]) == {"ods_tj_usb", "ods_tj_jlb"}
    assert set(result["item_code"]) == {"000003", "JCJG", "ZJJL"}
    assert "甲状腺结节" in result["result_value_raw"].tolist()
    assert "建议复查甲状腺超声" in result["result_value_raw"].tolist()
