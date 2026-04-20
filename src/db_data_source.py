"""Query HIS production database for exam data in a format compatible with P0Preprocessor."""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.db_connector import DBConnector
from src.utils import setup_logger

logger = setup_logger("db_data_source")

# Column mapping to match P0Preprocessor output format
OUTPUT_COLUMNS = [
    "study_id", "exam_time", "package_name", "patient_name", "gender", "birth_date",
    "dept_code", "dept_name", "source_table",
    "major_item_code", "major_item_name",
    "item_code", "item_name", "item_name_en",
    "result_value_raw", "unit_raw", "reference_range_raw", "abnormal_flag",
]

TEXT_RESULT_TABLES = {
    "ods_tj_usb",
    "ods_tj_jlb",
}


class DBDataSource:
    """Query exam data from the HIS database.

    Produces DataFrames with the same column schema as P0Preprocessor output,
    allowing the existing L1/L2/L4 pipeline to consume DB data directly.
    """

    def __init__(self, db: DBConnector, config: dict[str, Any] | None = None) -> None:
        self.db = db
        self.config = config or {}
        self._table_columns_cache: dict[str, set[str]] = {}

    def _get_table_columns(self, table: str) -> set[str]:
        if table not in self._table_columns_cache:
            df = self.db.execute_query(f"SHOW COLUMNS FROM `{table}`")
            fields = set(df["Field"].astype(str).tolist()) if not df.empty and "Field" in df.columns else set()
            self._table_columns_cache[table] = fields
        return self._table_columns_cache[table]

    def _choose_result_column(self, table: str, candidates: list[str]) -> str | None:
        columns = self._get_table_columns(table)
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    def query_by_study_id(self, study_id: str) -> pd.DataFrame:
        """Query all exam results for a single visit (StudyID)."""
        logger.info("Querying study_id=%s", study_id)
        frames = []

        # HY (化验室) — has SFXMDM, ItemResult, ItemUnit, DefValue, Flag
        hyb = self.db.execute_query("""
            SELECT j.ID as study_id, COALESCE(j.JCRQ, j.YYRQ) as exam_time, j.XM as patient_name,
                   j.XB as gender, j.CSNY as birth_date,
                   x.XMMC as package_name,
                   'HY' as dept_code, '化验室' as dept_name, 'ods_tj_hyb' as source_table,
                   s.SFXMDM as major_item_code, s.SFXMMC as major_item_name,
                   m.XXDM as item_code, m.XXMC as item_name, m.EXXMC as item_name_en,
                   h.ItemResult as result_value_raw,
                   COALESCE(NULLIF(h.ItemUnit, ''), m.Unit) as unit_raw,
                   h.DefValue as reference_range_raw,
                   h.Flag as abnormal_flag
            FROM ods_tj_hyb h
            JOIN ods_tj_jcxx j ON j.ID = h.StudyID
            LEFT JOIN ods_tj_jcmxx m ON h.XXDM = m.XXDM
            LEFT JOIN ods_tj_sfxm s ON h.SFXMDM = s.SFXMDM
            LEFT JOIN ods_tj_xmzh x ON j.ZHXMDM = x.XMDM
            WHERE h.StudyID = %s AND h.ItemResult IS NOT NULL AND h.ItemResult != ''
        """, (study_id,))
        if not hyb.empty:
            frames.append(hyb)

        # Other dept tables — have XXDM + CValue only
        dept_tables = {
            "YB": ("ods_tj_ybb", "一般检查"),
            "ER": ("ods_tj_erb", "人体成份"),
            "NK": ("ods_tj_nkb", "内科"),
            "WK": ("ods_tj_wkb", "外科"),
            "FK": ("ods_tj_fkb", "妇科"),
        }
        for dept_code, (table, dept_name) in dept_tables.items():
            dept_df = self.db.execute_query(f"""
                SELECT j.ID as study_id, COALESCE(j.JCRQ, j.YYRQ) as exam_time, j.XM as patient_name,
                       j.XB as gender, j.CSNY as birth_date,
                       x.XMMC as package_name,
                       '{dept_code}' as dept_code, '{dept_name}' as dept_name,
                       '{table}' as source_table,
                       '' as major_item_code, '' as major_item_name,
                       m.XXDM as item_code, m.XXMC as item_name, m.EXXMC as item_name_en,
                       d.CValue as result_value_raw,
                       m.Unit as unit_raw,
                       '' as reference_range_raw,
                       NULL as abnormal_flag
                FROM `{table}` d
                JOIN ods_tj_jcxx j ON j.ID = d.StudyID
                LEFT JOIN ods_tj_jcmxx m ON d.XXDM = m.XXDM
                LEFT JOIN ods_tj_xmzh x ON j.ZHXMDM = x.XMDM
                WHERE d.StudyID = %s AND d.CValue IS NOT NULL AND d.CValue != ''
            """, (study_id,))
            if not dept_df.empty:
                frames.append(dept_df)

        text_tables = {
            "ods_tj_usb": ("US", "彩超室"),
            "ods_tj_jlb": ("JL", "总检室"),
        }
        for table, (dept_code, dept_name) in text_tables.items():
            if table == "ods_tj_usb":
                result_col = self._choose_result_column(table, ["CValue", "ItemResult", "ResultValue"])
                if not result_col:
                    logger.warning("Skip %s because no known result column was found", table)
                    continue
                text_df = self.db.execute_query(f"""
                    SELECT j.ID as study_id, COALESCE(j.JCRQ, j.YYRQ) as exam_time, j.XM as patient_name,
                           j.XB as gender, j.CSNY as birth_date,
                           x.XMMC as package_name,
                           '{dept_code}' as dept_code, '{dept_name}' as dept_name,
                           '{table}' as source_table,
                           '' as major_item_code, '' as major_item_name,
                           m.XXDM as item_code, m.XXMC as item_name, m.EXXMC as item_name_en,
                           d.{result_col} as result_value_raw,
                           COALESCE(m.Unit, '') as unit_raw,
                           '' as reference_range_raw,
                           NULL as abnormal_flag
                    FROM `{table}` d
                    JOIN ods_tj_jcxx j ON j.ID = d.StudyID
                    LEFT JOIN ods_tj_jcmxx m ON d.XXDM = m.XXDM
                    LEFT JOIN ods_tj_xmzh x ON j.ZHXMDM = x.XMDM
                    WHERE d.StudyID = %s AND d.{result_col} IS NOT NULL AND d.{result_col} != ''
                """, (study_id,))
            else:
                columns = self._get_table_columns(table)
                select_parts: list[str] = []
                if "JCJG" in columns:
                    select_parts.append(f"""
                        SELECT j.ID as study_id, COALESCE(j.JCRQ, j.YYRQ) as exam_time, j.XM as patient_name,
                               j.XB as gender, j.CSNY as birth_date,
                               x.XMMC as package_name,
                               '{dept_code}' as dept_code, '{dept_name}' as dept_name,
                               '{table}' as source_table,
                               '' as major_item_code, '' as major_item_name,
                               'JCJG' as item_code, '异常结果汇总' as item_name, 'JCJG' as item_name_en,
                               d.JCJG as result_value_raw,
                               '' as unit_raw,
                               '' as reference_range_raw,
                               NULL as abnormal_flag
                        FROM `{table}` d
                        JOIN ods_tj_jcxx j ON j.ID = d.StudyID
                        LEFT JOIN ods_tj_xmzh x ON j.ZHXMDM = x.XMDM
                        WHERE d.StudyID = %s AND d.JCJG IS NOT NULL AND d.JCJG != ''
                    """)
                if "ZJJL" in columns:
                    select_parts.append(f"""
                        SELECT j.ID as study_id, COALESCE(j.JCRQ, j.YYRQ) as exam_time, j.XM as patient_name,
                               j.XB as gender, j.CSNY as birth_date,
                               x.XMMC as package_name,
                               '{dept_code}' as dept_code, '{dept_name}' as dept_name,
                               '{table}' as source_table,
                               '' as major_item_code, '' as major_item_name,
                               'ZJJL' as item_code, '总检结论' as item_name, 'ZJJL' as item_name_en,
                               d.ZJJL as result_value_raw,
                               '' as unit_raw,
                               '' as reference_range_raw,
                               NULL as abnormal_flag
                        FROM `{table}` d
                        JOIN ods_tj_jcxx j ON j.ID = d.StudyID
                        LEFT JOIN ods_tj_xmzh x ON j.ZHXMDM = x.XMDM
                        WHERE d.StudyID = %s AND d.ZJJL IS NOT NULL AND d.ZJJL != ''
                    """)
                if not select_parts:
                    logger.warning("Skip %s because no known text columns were found", table)
                    continue
                union_sql = "\nUNION ALL\n".join(select_parts)
                text_df = self.db.execute_query(union_sql, tuple([study_id] * len(select_parts)))
            if not text_df.empty:
                frames.append(text_df)

        if not frames:
            logger.warning("No data found for study_id=%s", study_id)
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        result = pd.concat(frames, ignore_index=True)
        logger.info("study_id=%s: %d rows from %d dept(s)", study_id, len(result), len(frames))
        return result

    def query_by_patient(self, sfzh: str) -> list[pd.DataFrame]:
        """Query all exam visits for a patient (by ID card number).

        Returns a list of DataFrames, one per visit, sorted by exam_time.
        """
        logger.info("Querying patient sfzh=%s...", sfzh[:4] + "****")
        visits = self.db.execute_query(
            "SELECT ID FROM ods_tj_jcxx WHERE SFZH = %s ORDER BY JCRQ", (sfzh,)
        )
        if visits.empty:
            logger.warning("No visits found for patient")
            return []

        study_ids = visits["ID"].tolist()
        logger.info("Found %d visit(s)", len(study_ids))
        results = []
        for sid in study_ids:
            df = self.query_by_study_id(str(sid))
            if not df.empty:
                results.append(df)
        return results

    def query_by_date_range(
        self, start_date: str, end_date: str, limit: int = 10000
    ) -> pd.DataFrame:
        """Query HY exam results within a date range (for batch processing).

        Only queries hyb (化验室) as it's the primary structured data source.
        """
        logger.info("Querying hyb date range %s to %s (limit %d)", start_date, end_date, limit)
        df = self.db.execute_query("""
            SELECT j.ID as study_id, COALESCE(j.JCRQ, j.YYRQ) as exam_time, j.XM as patient_name,
                   j.XB as gender, j.CSNY as birth_date,
                   x.XMMC as package_name,
                   'HY' as dept_code, '化验室' as dept_name, 'ods_tj_hyb' as source_table,
                   s.SFXMDM as major_item_code, s.SFXMMC as major_item_name,
                   m.XXDM as item_code, m.XXMC as item_name, m.EXXMC as item_name_en,
                   h.ItemResult as result_value_raw,
                   COALESCE(NULLIF(h.ItemUnit, ''), m.Unit) as unit_raw,
                   h.DefValue as reference_range_raw,
                   h.Flag as abnormal_flag
            FROM ods_tj_hyb h
            JOIN ods_tj_jcxx j ON j.ID = h.StudyID
            LEFT JOIN ods_tj_jcmxx m ON h.XXDM = m.XXDM
            LEFT JOIN ods_tj_sfxm s ON h.SFXMDM = s.SFXMDM
            LEFT JOIN ods_tj_xmzh x ON j.ZHXMDM = x.XMDM
            WHERE h.CheckDate BETWEEN %s AND %s
                  AND h.ItemResult IS NOT NULL AND h.ItemResult != ''
            LIMIT %s
        """, (start_date, end_date, limit))
        logger.info("Date range query: %d rows", len(df))
        return df if not df.empty else pd.DataFrame(columns=OUTPUT_COLUMNS)
