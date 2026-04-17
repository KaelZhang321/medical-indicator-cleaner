from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from src.dict_manager import DictManager
from src.utils import ensure_dir, setup_logger


class L2EmbeddingMatcher:
    """Sentence-BERT + FAISS based semantic retriever."""

    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        cache_dir: str = "./models",
        sentence_transformer_cls: type | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir
        self.sentence_transformer_cls = sentence_transformer_cls
        self.logger = setup_logger(self.__class__.__name__)
        self.model = self._load_model()
        self.index: faiss.IndexFlatIP | None = None
        self.index_labels: list[str] = []
        self.index_names: list[str] = []
        self.code_to_info: dict[str, dict[str, str]] = {}

    def _load_model(self):
        cls = self.sentence_transformer_cls
        if cls is None:
            from sentence_transformers import SentenceTransformer

            cls = SentenceTransformer
        return cls(self.model_name, device=self.device, cache_folder=self.cache_dir)

    def _encode(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, normalize_embeddings=False)
        vectors = np.asarray(embeddings, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def build_index(self, dict_manager: DictManager) -> None:
        texts: list[str] = []
        labels: list[str] = []
        self.code_to_info = {}

        for row in dict_manager.standard_dict.itertuples(index=False):
            self.code_to_info[row.code] = {
                "standard_name": row.standard_name,
                "category": row.category,
            }

            candidates = [row.standard_name]
            if row.abbreviation:
                candidates.append(row.abbreviation)
            candidates.extend([alias for alias in str(row.aliases).split(";") if alias.strip()])

            for text in candidates:
                normalized = str(text).strip()
                if not normalized:
                    continue
                texts.append(normalized)
                labels.append(row.code)

        vectors = self._encode(texts)
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        self.index_labels = labels
        self.index_names = texts
        self.logger.info(
            "Built embedding index: standard_items=%s vectors=%s",
            len(dict_manager.standard_dict),
            self.index.ntotal,
        )

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self.is_index_loaded():
            raise ValueError("FAISS index is not loaded")

        query_vector = self._encode([query])
        search_k = min(max(top_k * 3, top_k), len(self.index_labels))
        scores, indices = self.index.search(query_vector, search_k)
        return self._deduplicate_results(scores[0], indices[0], top_k)

    def search_batch(self, queries: list[str], top_k: int = 5) -> list[list[dict[str, Any]]]:
        if not self.is_index_loaded():
            raise ValueError("FAISS index is not loaded")

        query_vectors = self._encode(queries)
        search_k = min(max(top_k * 3, top_k), len(self.index_labels))
        scores, indices = self.index.search(query_vectors, search_k)
        return [self._deduplicate_results(score_row, index_row, top_k) for score_row, index_row in zip(scores, indices)]

    def _deduplicate_results(
        self,
        scores: np.ndarray,
        indices: np.ndarray,
        top_k: int,
    ) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for score, index in zip(scores, indices):
            if index < 0:
                continue
            standard_code = self.index_labels[int(index)]
            if standard_code in deduped and deduped[standard_code]["score"] >= float(score):
                continue

            code_info = self.code_to_info[standard_code]
            deduped[standard_code] = {
                "standard_code": standard_code,
                "standard_name": code_info["standard_name"],
                "category": code_info["category"],
                "matched_text": self.index_names[int(index)],
                "score": float(score),
            }

        results = sorted(deduped.values(), key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def save_index(self, dir_path: str) -> None:
        if not self.is_index_loaded():
            raise ValueError("FAISS index is not loaded")

        target = Path(dir_path)
        ensure_dir(target)
        faiss.write_index(self.index, str(target / "faiss.index"))
        metadata = {
            "labels": self.index_labels,
            "names": self.index_names,
            "code_to_info": self.code_to_info,
        }
        with (target / "metadata.pkl").open("wb") as file:
            pickle.dump(metadata, file)

    def load_index(self, dir_path: str) -> None:
        target = Path(dir_path)
        self.index = faiss.read_index(str(target / "faiss.index"))
        with (target / "metadata.pkl").open("rb") as file:
            metadata = pickle.load(file)
        self.index_labels = metadata["labels"]
        self.index_names = metadata["names"]
        self.code_to_info = metadata["code_to_info"]

    def is_index_loaded(self) -> bool:
        return self.index is not None
