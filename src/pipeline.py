from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.ai_review import AIReviewProcessor, ArkChatClient
from src.dict_manager import DictManager
from src.l1_rule_cleaner import CleanResult, L1RuleCleaner
from src.l2_embedding_matcher import L2EmbeddingMatcher
from src.l4_review import L4Review
from src.p0_preprocessor import P0Preprocessor
from src.utils import load_config


class StandardizationPipeline:
    """Orchestrate P0/L1/L2/L4 normalization stages."""

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        matcher: Any | None = None,
        ai_reviewer: Any | None = None,
        output_dir: str | None = None,
        strict: bool | None = None,
    ) -> None:
        self.config = load_config(config_path)
        preprocessing_cfg = self.config.get("preprocessing", {})
        self.strict = bool(preprocessing_cfg.get("strict", True)) if strict is None else strict
        self.config.setdefault("preprocessing", {})["strict"] = self.strict
        self.output_dir = output_dir or self.config["data"]["output_dir"]
        self.dict_manager = DictManager(
            self.config["data"]["standard_dict"],
            self.config["data"]["alias_dict"],
        )
        self.preprocessor = P0Preprocessor(self.config)
        self.cleaner = L1RuleCleaner(self.dict_manager)
        self.matcher = matcher or self._init_matcher()
        self.ai_reviewer = ai_reviewer or self._init_ai_reviewer()
        self.reviewer = L4Review(
            auto_threshold=float(self.config["thresholds"]["auto_map"]),
            review_threshold=float(self.config["thresholds"]["need_review"]),
        )

    def _init_matcher(self) -> L2EmbeddingMatcher:
        index_path = Path(self.config["index"]["path"])
        if not (index_path / "faiss.index").exists() or not (index_path / "metadata.pkl").exists():
            return NullMatcher()

        matcher = L2EmbeddingMatcher(
            model_name=self.config["model"]["name"],
            device=self.config["model"].get("device", "cpu"),
            cache_dir=self.config["model"].get("cache_dir", "./models"),
        )
        matcher.load_index(str(index_path))
        return matcher

    def _init_ai_reviewer(self) -> AIReviewProcessor:
        ai_review_cfg = self.config.get("ai_review", {})
        enabled = bool(ai_review_cfg.get("enabled", False))
        model = ai_review_cfg.get("model", "")
        client = ArkChatClient(model=model)
        return AIReviewProcessor(
            enabled=enabled,
            client=client,
            standard_dict=self.dict_manager.standard_dict[["code", "standard_name", "category"]],
        )

    def run(self, input_path: str, output_dir: str | None = None) -> dict[str, Any]:
        path = Path(input_path)
        if path.is_dir():
            return self.run_batch(str(path), output_dir=output_dir)

        dataframe = self._load_input_dataframe(path)
        results = self._standardize_dataframe(dataframe)
        results = self.ai_reviewer.review(results)
        classified = self.reviewer.classify(results)
        self.reviewer.export_csv(classified, output_dir or self.output_dir)
        self._print_report(classified)
        return classified

    def run_batch(self, input_dir: str, output_dir: str | None = None) -> dict[str, Any]:
        paths = sorted(Path(input_dir).glob("*.json"))
        frames = [self.preprocessor.process_file(str(path)) for path in paths]
        dataframe = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["item_name"])
        results = self._standardize_dataframe(dataframe)
        results = self.ai_reviewer.review(results)
        classified = self.reviewer.classify(results)
        self.reviewer.export_csv(classified, output_dir or self.output_dir)
        self._print_report(classified)
        return classified

    def _load_input_dataframe(self, path: Path) -> pd.DataFrame:
        if path.suffix.lower() == ".csv":
            dataframe = pd.read_csv(path)
            if "item_name" not in dataframe.columns:
                raise ValueError("CSV input must contain an item_name column")
            return dataframe.fillna("")

        return self.preprocessor.process_file(str(path))

    def _standardize_dataframe(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        names = dataframe["item_name"].fillna("").astype(str).tolist()
        clean_results = self.cleaner.clean_batch(names)
        base_results: list[dict[str, Any]] = []
        for clean_result, (_, row) in zip(clean_results, dataframe.iterrows()):
            base_results.append(self._result_from_clean(clean_result, row.to_dict()))

        pending_indices = [index for index, row in enumerate(base_results) if row["confidence"] < 1.0]
        if not pending_indices or not self.matcher.is_index_loaded():
            return base_results

        pending_queries = [base_results[index]["cleaned_name"] for index in pending_indices]
        if hasattr(self.matcher, "search_batch"):
            batch_candidates = self.matcher.search_batch(pending_queries, top_k=int(self.config["index"]["top_k"]))
        else:
            batch_candidates = [self.matcher.search(query, top_k=int(self.config["index"]["top_k"])) for query in pending_queries]

        for index, candidates in zip(pending_indices, batch_candidates):
            self._apply_l2_result(base_results[index], candidates)

        return base_results

    def _result_from_clean(self, clean_result: CleanResult, row: dict[str, Any]) -> dict[str, Any]:
        base = {
            **row,
            "original_name": clean_result.original,
            "cleaned_name": clean_result.cleaned,
            "abbreviation": clean_result.abbreviation or "",
            "standard_name": clean_result.standard_name or "",
            "standard_code": clean_result.standard_code or "",
            "category": clean_result.category or "",
            "standard_unit": "",
            "result_type": "",
            "confidence": clean_result.confidence,
            "match_source": clean_result.match_source,
            "top_candidates": [],
        }
        if clean_result.confidence >= 1.0:
            standard_row = self.dict_manager.standard_dict.loc[
                self.dict_manager.standard_dict["code"] == clean_result.standard_code
            ].iloc[0]
            base["standard_unit"] = standard_row["common_unit"]
            base["result_type"] = standard_row["result_type"]
            return base
        return base

    def _apply_l2_result(self, base: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
        base["top_candidates"] = candidates
        if not candidates:
            return

        top = candidates[0]
        base.update(
            {
                "standard_name": top["standard_name"],
                "standard_code": top["standard_code"],
                "category": top["category"],
                "confidence": top["score"],
                "match_source": "l2_embedding",
            }
        )
        standard_row = self.dict_manager.standard_dict.loc[
            self.dict_manager.standard_dict["code"] == top["standard_code"]
        ].iloc[0]
        base["standard_unit"] = standard_row["common_unit"]
        base["result_type"] = standard_row["result_type"]

    def _print_report(self, classified: dict[str, Any]) -> None:
        stats = classified["stats"]
        total = stats["total"] or 1
        print("========= 标准化统计报告 =========")
        print(f"总指标数:        {stats['total']}")
        print(f"L1 命中数:       {stats['l1_hit_count']} ({stats['l1_hit_rate']:.1%})")
        print(f"L2 命中数:       {stats.get('l2_hit_count', 0)} ({stats.get('l2_hit_rate', 0.0):.1%})")
        print(f"自动归一:        {stats['auto_count']} ({stats['auto_count'] / total:.1%})")
        print(f"待人工审核:      {stats['review_count']} ({stats['review_count'] / total:.1%})")
        print(f"需人工处理:      {stats['manual_count']} ({stats['manual_count'] / total:.1%})")
        print("=================================")


class NullMatcher:
    """No-op matcher used when the FAISS index has not been built yet."""

    def is_index_loaded(self) -> bool:
        return False

    def search(self, _query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return []
