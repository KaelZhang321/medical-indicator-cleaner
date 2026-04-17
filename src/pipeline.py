from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

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
        output_dir: str | None = None,
    ) -> None:
        self.config = load_config(config_path)
        self.output_dir = output_dir or self.config["data"]["output_dir"]
        self.dict_manager = DictManager(
            self.config["data"]["standard_dict"],
            self.config["data"]["alias_dict"],
        )
        self.preprocessor = P0Preprocessor(self.config)
        self.cleaner = L1RuleCleaner(self.dict_manager)
        self.matcher = matcher or self._init_matcher()
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

    def run(self, input_path: str, output_dir: str | None = None) -> dict[str, Any]:
        path = Path(input_path)
        if path.is_dir():
            return self.run_batch(str(path), output_dir=output_dir)

        names = self._load_input_names(path)
        results = self._standardize_names(names)
        classified = self.reviewer.classify(results)
        self.reviewer.export_csv(classified, output_dir or self.output_dir)
        self._print_report(classified)
        return classified

    def run_batch(self, input_dir: str, output_dir: str | None = None) -> dict[str, Any]:
        paths = sorted(Path(input_dir).glob("*.json"))
        frames = [self.preprocessor.process_file(str(path)) for path in paths]
        dataframe = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["item_name"])
        names = dataframe["item_name"].fillna("").astype(str).tolist()
        results = self._standardize_names(names)
        classified = self.reviewer.classify(results)
        self.reviewer.export_csv(classified, output_dir or self.output_dir)
        self._print_report(classified)
        return classified

    def _load_input_names(self, path: Path) -> list[str]:
        if path.suffix.lower() == ".csv":
            dataframe = pd.read_csv(path)
            if "item_name" not in dataframe.columns:
                raise ValueError("CSV input must contain an item_name column")
            return dataframe["item_name"].fillna("").astype(str).tolist()

        dataframe = self.preprocessor.process_file(str(path))
        return dataframe["item_name"].fillna("").astype(str).tolist()

    def _standardize_names(self, names: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for name in names:
            clean_result = self.cleaner.clean(name)
            results.append(self._result_from_clean(clean_result))
        return results

    def _result_from_clean(self, clean_result: CleanResult) -> dict[str, Any]:
        base = {
            "original_name": clean_result.original,
            "cleaned_name": clean_result.cleaned,
            "abbreviation": clean_result.abbreviation or "",
            "standard_name": clean_result.standard_name or "",
            "standard_code": clean_result.standard_code or "",
            "category": clean_result.category or "",
            "confidence": clean_result.confidence,
            "match_source": clean_result.match_source,
            "top_candidates": [],
        }
        if clean_result.confidence >= 1.0:
            return base

        if not self.matcher.is_index_loaded():
            return base

        candidates = self.matcher.search(clean_result.cleaned, top_k=int(self.config["index"]["top_k"]))
        base["top_candidates"] = candidates
        if candidates:
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
        return base

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
