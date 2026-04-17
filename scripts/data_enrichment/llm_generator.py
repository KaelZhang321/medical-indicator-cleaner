"""Use LLM (Volcengine Ark / doubao) to batch-generate medical indicator data."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from src.ai_review import ArkChatClient
from src.utils import ensure_dir, setup_logger

logger = setup_logger("llm_generator")


class LLMGenerator:
    """Batch-generate data assets via LLM API calls."""

    def __init__(self, model: str = "doubao-seed-2-0-pro-260215", delay: float = 0.5, client: Any | None = None) -> None:
        self.client = client or ArkChatClient(model=model)
        self.delay = delay
        if not self.client.is_configured():
            raise RuntimeError("ARK_API_KEY not set. Export it before running: export ARK_API_KEY='your-key'")

    def _call(self, system: str, user: str) -> dict[str, Any]:
        """Call LLM and return parsed JSON, with retry on transient errors."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(3):
            try:
                result = self.client.complete_json(messages)
                time.sleep(self.delay)
                return result
            except Exception as exc:
                logger.warning("API call failed (attempt %d): %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
        return {}

    # ------------------------------------------------------------------
    # Task 1: Expand aliases for existing standard_dict entries
    # ------------------------------------------------------------------

    def generate_aliases(self, standard_dict: pd.DataFrame, output_path: str) -> dict[str, list[str]]:
        """For each indicator, ask LLM to generate additional aliases."""
        results = self._load_existing_dict(output_path)
        system = (
            "你是医学检验专家。用户会给你一个检验指标信息，请补充更多中文别名、英文缩写变体、"
            "常见错别字、口语化叫法。返回 JSON: {\"aliases\": [\"别名1\", \"别名2\", ...]}。"
            "不要重复用户已给出的别名。只返回 JSON。"
        )
        for row in tqdm(standard_dict.itertuples(index=False), total=len(standard_dict), desc="生成别名"):
            if row.code in results:
                continue
            user = json.dumps({
                "standard_name": row.standard_name,
                "abbreviation": row.abbreviation,
                "existing_aliases": row.aliases,
                "category": row.category,
            }, ensure_ascii=False)
            resp = self._call(system, user)
            new_aliases = resp.get("aliases", [])
            if new_aliases:
                results[row.code] = [a.strip() for a in new_aliases if a.strip()]
                logger.info("%s: +%d aliases", row.code, len(results[row.code]))
                self._write_json(output_path, results)

        self._write_json(output_path, results)
        logger.info("Aliases saved to %s (%d entries)", output_path, len(results))
        return results

    # ------------------------------------------------------------------
    # Task 2: Generate reference ranges for all indicators
    # ------------------------------------------------------------------

    def generate_reference_ranges(self, standard_dict: pd.DataFrame, output_path: str) -> list[dict]:
        """Generate standard reference ranges for each numeric indicator."""
        results = self._load_existing_list(output_path)
        existing_codes = {item.get("standard_code", "") for item in results}
        system = (
            "你是医学检验专家。为给定检验指标提供标准参考范围。返回 JSON:\n"
            '{"general": {"ref_min": number, "ref_max": number}, '
            '"male": {"ref_min": number, "ref_max": number} 或 null, '
            '"female": {"ref_min": number, "ref_max": number} 或 null, '
            '"notes": "特殊说明"}\n'
            "如果该指标是定性指标（如阴性/阳性），ref_min 和 ref_max 设为 null，notes 中说明正常值。"
            "只返回 JSON。"
        )
        numeric_rows = standard_dict[standard_dict["result_type"].isin(["numeric", "mixed"])]
        for row in tqdm(numeric_rows.itertuples(index=False), total=len(numeric_rows), desc="生成参考范围"):
            if row.code in existing_codes:
                continue
            user = json.dumps({
                "standard_name": row.standard_name,
                "abbreviation": row.abbreviation,
                "unit": row.common_unit,
                "category": row.category,
            }, ensure_ascii=False)
            resp = self._call(system, user)
            if resp:
                resp["standard_code"] = row.code
                resp["standard_name"] = row.standard_name
                resp["unit"] = row.common_unit
                results.append(resp)
                self._write_json(output_path, results)

        self._write_json(output_path, results)
        logger.info("Reference ranges saved to %s (%d entries)", output_path, len(results))
        return results

    # ------------------------------------------------------------------
    # Task 3: Generate risk weights for all indicators
    # ------------------------------------------------------------------

    def generate_risk_weights(self, standard_dict: pd.DataFrame, output_path: str) -> list[dict]:
        """Generate risk weight and category for each indicator."""
        results = self._load_existing_list(output_path)
        existing_codes = {item.get("standard_code", "") for item in results}
        system = (
            "你是临床医学专家。评估给定检验指标异常时的健康风险程度。返回 JSON:\n"
            '{"risk_weight": float(0.0-1.0), "risk_category": "critical"|"warning"|"info", '
            '"reason": "一句话理由"}\n'
            "risk_weight 越高表示该指标异常时越需要关注。只返回 JSON。"
        )
        for row in tqdm(standard_dict.itertuples(index=False), total=len(standard_dict), desc="生成风险权重"):
            if row.code in existing_codes:
                continue
            user = json.dumps({
                "standard_name": row.standard_name,
                "abbreviation": row.abbreviation,
                "category": row.category,
            }, ensure_ascii=False)
            resp = self._call(system, user)
            if resp:
                resp["standard_code"] = row.code
                results.append(resp)
                self._write_json(output_path, results)

        self._write_json(output_path, results)
        logger.info("Risk weights saved to %s (%d entries)", output_path, len(results))
        return results

    # ------------------------------------------------------------------
    # Task 4: Generate new indicators missing from the current dict
    # ------------------------------------------------------------------

    def generate_new_indicators(self, existing_codes: set[str], output_path: str) -> list[dict]:
        """Ask LLM to produce common indicators not yet in the dictionary."""
        system = (
            "你是医学检验专家。用户会告诉你已有的指标类别，请补充该类别中缺失的常见检验指标。"
            "返回 JSON: {\"indicators\": [{\"standard_name\": str, \"abbreviation\": str, "
            "\"aliases\": \"别名1;别名2\", \"category\": str, \"common_unit\": str, "
            "\"result_type\": \"numeric\"|\"qualitative\"|\"mixed\"}]}\n只返回 JSON。"
        )
        categories_to_expand = [
            ("电解质", "目前缺失。请补充：钾K、钠Na、氯Cl、钙Ca、磷P、镁Mg、碳酸氢根HCO3等"),
            ("心肌标志物", "目前缺失。请补充：CK、CK-MB、LDH、cTnI、cTnT、BNP、NT-proBNP、肌红蛋白MYO等"),
            ("炎症指标", "目前缺失。请补充：CRP、hs-CRP、ESR(血沉)、PCT(降钙素原)等"),
            ("乙肝五项", "目前缺失。请补充：HBsAg、HBsAb、HBeAg、HBeAb、HBcAb"),
            ("血常规补充", "目前已有WBC/RBC/HGB/PLT/PDW。请补充缺失的：HCT、MCV、MCH、MCHC、MPV、RDW-CV、RDW-SD、PCT、嗜酸性粒细胞、嗜碱性粒细胞、中性粒细胞、淋巴细胞、单核细胞等"),
            ("男性特有", "目前缺失。请补充：PSA(前列腺特异性抗原)、f-PSA、PSA比值等"),
            ("糖代谢补充", "目前已有FPG和HbA1c。请补充：餐后2小时血糖2hPG、糖化白蛋白GA、空腹胰岛素INS、C肽C-peptide等"),
            ("肝功能补充", "目前已有ALT/AST/GGT/ALP/TBIL/DBIL/IBIL/TP/ALB/GLB。请补充：前白蛋白PA、胆汁酸TBA、腺苷脱氨酶ADA等"),
        ]

        all_indicators = self._load_existing_list(output_path)
        seen_names = {item.get("standard_name", "") for item in all_indicators}
        for category, hint in tqdm(categories_to_expand, desc="生成新增指标"):
            user = json.dumps({"category": category, "hint": hint}, ensure_ascii=False)
            resp = self._call(system, user)
            indicators = resp.get("indicators", [])
            for indicator in indicators:
                if indicator.get("standard_name", "") in seen_names:
                    continue
                if not indicator.get("category"):
                    indicator["category"] = category
                all_indicators.append(indicator)
                seen_names.add(indicator.get("standard_name", ""))
            logger.info("%s: +%d indicators", category, len(indicators))
            self._write_json(output_path, all_indicators)

        self._write_json(output_path, all_indicators)
        logger.info("New indicators saved to %s (%d entries)", output_path, len(all_indicators))
        return all_indicators

    def _load_existing_dict(self, path: str) -> dict[str, list[str]]:
        file_path = Path(path)
        if not file_path.exists():
            return {}
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _load_existing_list(self, path: str) -> list[dict]:
        file_path = Path(path)
        if not file_path.exists():
            return []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _write_json(self, path: str, payload: Any) -> None:
        ensure_dir(Path(path).parent)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
