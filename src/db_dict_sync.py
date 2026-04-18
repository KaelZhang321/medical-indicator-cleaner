"""Synchronize standard dictionaries from the HIS production database."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.db_connector import DBConnector
from src.l1_rule_cleaner import L1RuleCleaner
from src.utils import ensure_dir, setup_logger

logger = setup_logger("db_dict_sync")

# LBDM prefix → human-readable category
LBDM_CATEGORY_MAP = {
    "0101": "一般检查",
    "0301": "血常规",
    "0302": "尿常规",
    "0303": "糖代谢",
    "0307": "特殊生化",
    "0308": "重金属/微量元素",
    "0401": "代谢指数",
    "0402": "血脂",
    "0403": "电解质/微量元素",
    "0404": "肾功能",
    "0405": "肝功能",
    "0406": "胰腺功能",
    "0409": "心肌标志物/炎症",
    "0411": "免疫球蛋白/补体",
    "0412": "特殊检验",
    "0501": "肝炎病毒",
    "0502": "性激素",
    "0507": "甲状腺功能",
    "0508": "脑脊液",
    "0509": "肿瘤标志物",
    "0510": "风湿免疫",
    "0511": "感染标志物",
    "0514": "营养/感染/其他",
    "0601": "血液流变学",
    "0801": "血型",
    "0901": "HPV检测",
    "1049": "动脉硬化",
    "1701": "口腔检查",
    "1801": "耳鼻喉",
    "1901": "外科",
    "1950": "人体成分",
    "2001": "眼科",
    "2101": "皮肤科",
    "2201": "妇科",
    "2202": "妇科特检",
    "2701": "健康问诊",
    "2900": "食物不耐受",
    "3000": "食物不耐受",
    "3001": "过敏原检测",
    "3200": "基因检测",
    "3400": "内科",
    "3401": "内科补充",
    "901": "凝血功能",
    "902": "凝血功能",
    "903": "凝血功能",
    "904": "白带/分泌物",
    "905": "白带/分泌物",
    "906": "细胞学",
    "907": "病理",
    "908": "特殊染色",
    "909": "分子检测",
}


def _guess_category(lbdm: str) -> str:
    """Map LBDM code to a readable category name."""
    if not lbdm:
        return "其他"
    # Try exact match first, then prefix match
    if lbdm in LBDM_CATEGORY_MAP:
        return LBDM_CATEGORY_MAP[lbdm]
    for prefix_len in [3, 2]:
        prefix = lbdm[:prefix_len]
        if prefix in LBDM_CATEGORY_MAP:
            return LBDM_CATEGORY_MAP[prefix]
    return "其他"


def _guess_result_type(xxmc: str, unit: str) -> str:
    """Guess whether an indicator is numeric, qualitative, or mixed."""
    qualitative_keywords = ["血型", "霉菌", "滴虫", "清洁度", "颜色", "浊度", "检查所见", "检查描述"]
    if any(kw in (xxmc or "") for kw in qualitative_keywords):
        return "qualitative"
    if unit and unit.strip():
        return "numeric"
    return "mixed"


def _clean_item_name(xxmc: str) -> tuple[str, str]:
    """Apply basic L1-style cleaning to extract clean name and abbreviation.

    Returns (cleaned_name, abbreviation).
    """
    name = (xxmc or "").strip()
    # Remove ★
    name = name.lstrip("★").strip()
    # Fullwidth → halfwidth brackets
    name = name.replace("（", "(").replace("）", ")")
    # Extract abbreviation from trailing (ENGLISH)
    match = re.match(r"^(.+?)\(([A-Za-z0-9\-\.β/#%≥≤\s]+)\)$", name)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return name, ""


class DictSyncer:
    """Synchronize dictionaries from HIS database to local CSV files."""

    def __init__(self, db: DBConnector) -> None:
        self.db = db

    def sync_standard_dict(self, output_path: str) -> pd.DataFrame:
        """Build standard_dict.csv from ods_tj_jcmxx (1956 indicators).

        Each row becomes a standard indicator with:
        - code: XXDM (original HIS item code)
        - standard_name: cleaned XXMC
        - abbreviation: extracted from brackets or EXXMC
        - aliases: original XXMC variants
        - category: derived from LBDM
        - common_unit: Unit field
        - result_type: numeric/qualitative/mixed
        """
        logger.info("Syncing standard_dict from ods_tj_jcmxx...")
        df = self.db.execute_query(
            "SELECT XXDM, XXMC, EXXMC, Unit, LBDM, XXValueType FROM ods_tj_jcmxx ORDER BY XXDM"
        )
        if df.empty:
            logger.warning("jcmxx returned 0 rows")
            return pd.DataFrame()

        rows: list[dict[str, str]] = []
        for _, row in df.iterrows():
            xxdm = str(row.get("XXDM", "")).strip()
            xxmc = str(row.get("XXMC", "")).strip()
            exxmc = str(row.get("EXXMC", "")).strip() if row.get("EXXMC") else ""
            unit = str(row.get("Unit", "")).strip() if row.get("Unit") else ""
            lbdm = str(row.get("LBDM", "")).strip() if row.get("LBDM") else ""

            if not xxdm or not xxmc:
                continue

            # Skip generic items like "检查所见", "检查描述", "其他"
            if xxmc in ("检查所见", "检查描述", "其他"):
                continue

            cleaned_name, bracket_abbr = _clean_item_name(xxmc)
            abbreviation = bracket_abbr or exxmc
            category = _guess_category(lbdm)
            result_type = _guess_result_type(xxmc, unit)

            # Build aliases: original name (if different from cleaned) + abbreviation variants
            aliases_set: list[str] = []
            if xxmc != cleaned_name:
                aliases_set.append(xxmc)
            # Original with brackets (common lookup form)
            if bracket_abbr and f"{cleaned_name}({bracket_abbr})" != xxmc:
                aliases_set.append(f"{cleaned_name}({bracket_abbr})")
            if exxmc and exxmc != abbreviation:
                aliases_set.append(exxmc)

            rows.append({
                "code": xxdm,
                "standard_name": cleaned_name,
                "abbreviation": abbreviation,
                "aliases": ";".join(aliases_set),
                "category": category,
                "common_unit": unit,
                "result_type": result_type,
            })

        result = pd.DataFrame(rows)
        ensure_dir(str(Path(output_path).parent))
        result.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info("Synced %d indicators to %s", len(result), output_path)
        return result

    def sync_major_item_dict(self, output_path: str) -> pd.DataFrame:
        """Build major_item_dict.csv from ods_tj_sfxm + ods_tj_ksbm."""
        logger.info("Syncing major_item_dict from ods_tj_sfxm...")
        df = self.db.execute_query("""
            SELECT s.SFXMDM as code, s.SFXMMC as standard_name, s.KSBM,
                   k.KSMC as dept_name
            FROM ods_tj_sfxm s
            LEFT JOIN ods_tj_ksbm k ON s.KSBM = k.KSBM
            ORDER BY s.SFXMDM
        """)
        if df.empty:
            return pd.DataFrame()

        rows: list[dict[str, str]] = []
        for _, row in df.iterrows():
            name = str(row.get("standard_name", "")).strip()
            if not name:
                continue
            # Clean: remove H- prefix, normalize brackets
            cleaned = name
            if cleaned.startswith("H-"):
                cleaned = cleaned[2:]
            cleaned = cleaned.replace("（", "(").replace("）", ")")

            rows.append({
                "code": str(row["code"]).strip(),
                "standard_name": cleaned,
                "aliases": name if name != cleaned else "",
                "category": str(row.get("dept_name", "")).strip(),
            })

        result = pd.DataFrame(rows)
        ensure_dir(str(Path(output_path).parent))
        result.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info("Synced %d major items to %s", len(result), output_path)
        return result

    def sync_reference_ranges(self, output_path: str, sample_size: int = 500000) -> pd.DataFrame:
        """Aggregate reference ranges from a recent sample of ods_tj_hyb.DefValue.

        Uses a LIMIT-based sample from recent data to avoid full-table GROUP BY
        on the 13M-row hyb table.
        """
        logger.info("Syncing reference ranges from ods_tj_hyb (recent %d rows)...", sample_size)
        df = self.db.execute_query("""
            SELECT XXDM, DefValue, ItemUnit, COUNT(*) as cnt
            FROM (
                SELECT XXDM, DefValue, ItemUnit
                FROM ods_tj_hyb
                WHERE DefValue IS NOT NULL AND DefValue != ''
                ORDER BY RowID DESC
                LIMIT %s
            ) recent
            GROUP BY XXDM, DefValue, ItemUnit
            ORDER BY XXDM, cnt DESC
        """, (sample_size,))
        if df.empty:
            return pd.DataFrame()

        # For each XXDM, keep the most common DefValue
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _, row in df.iterrows():
            xxdm = str(row["XXDM"]).strip()
            if xxdm in seen:
                continue
            seen.add(xxdm)

            def_value = str(row.get("DefValue", "")).strip()
            unit = str(row.get("ItemUnit", "")).strip() if row.get("ItemUnit") else ""

            # Parse simple range: "3.9-6.1" or "0.00-5.800"
            range_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*[-~～]\s*([+-]?\d+(?:\.\d+)?)$", def_value)
            if range_match:
                rows.append({
                    "standard_code": xxdm,
                    "gender": "all",
                    "age_min": 0,
                    "age_max": 150,
                    "ref_min": float(range_match.group(1)),
                    "ref_max": float(range_match.group(2)),
                    "unit": unit,
                    "notes": "",
                })
                continue

            # Parse less-than: "<1.0"
            lt_match = re.match(r"^<\s*([+-]?\d+(?:\.\d+)?)", def_value)
            if lt_match:
                rows.append({
                    "standard_code": xxdm,
                    "gender": "all",
                    "age_min": 0,
                    "age_max": 150,
                    "ref_min": None,
                    "ref_max": float(lt_match.group(1)),
                    "unit": unit,
                    "notes": def_value,
                })
                continue

            # Parse greater-than: ">90" or "≥90"
            gt_match = re.match(r"^[>≥]\s*([+-]?\d+(?:\.\d+)?)", def_value)
            if gt_match:
                rows.append({
                    "standard_code": xxdm,
                    "gender": "all",
                    "age_min": 0,
                    "age_max": 150,
                    "ref_min": float(gt_match.group(1)),
                    "ref_max": None,
                    "unit": unit,
                    "notes": def_value,
                })
                continue

            # Non-numeric reference (qualitative)
            if def_value:
                rows.append({
                    "standard_code": xxdm,
                    "gender": "all",
                    "age_min": 0,
                    "age_max": 150,
                    "ref_min": None,
                    "ref_max": None,
                    "unit": unit,
                    "notes": def_value,
                })

        result = pd.DataFrame(rows)
        ensure_dir(str(Path(output_path).parent))
        result.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info("Synced %d reference ranges to %s", len(result), output_path)
        return result
