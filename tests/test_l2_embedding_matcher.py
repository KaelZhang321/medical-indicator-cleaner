from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from src.dict_manager import DictManager
from src.l2_embedding_matcher import L2EmbeddingMatcher


class FakeSentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        self.vector_map = {
            "总胆固醇": np.array([1.0, 0.0, 0.0], dtype=np.float32),
            "TC": np.array([1.0, 0.0, 0.0], dtype=np.float32),
            "胆固醇": np.array([0.95, 0.05, 0.0], dtype=np.float32),
            "CHOL": np.array([0.9, 0.1, 0.0], dtype=np.float32),
            "谷丙转氨酶": np.array([0.0, 1.0, 0.0], dtype=np.float32),
            "ALT": np.array([0.0, 1.0, 0.0], dtype=np.float32),
            "GPT": np.array([0.0, 0.95, 0.05], dtype=np.float32),
            "白细胞计数": np.array([0.0, 0.0, 1.0], dtype=np.float32),
            "WBC": np.array([0.0, 0.0, 1.0], dtype=np.float32),
            "完全不相关的文本": np.array([0.58, 0.58, 0.58], dtype=np.float32),
        }

    def encode(self, texts, normalize_embeddings=False, **_kwargs):
        encoded = []
        for text in texts:
            vector = self.vector_map.get(text, np.array([0.33, 0.33, 0.34], dtype=np.float32))
            if normalize_embeddings:
                vector = vector / np.linalg.norm(vector)
            encoded.append(vector.astype(np.float32))
        return np.vstack(encoded)


def build_matcher() -> L2EmbeddingMatcher:
    return L2EmbeddingMatcher(
        model_name="fake-model",
        sentence_transformer_cls=FakeSentenceTransformer,
    )


def test_encode_shape() -> None:
    matcher = build_matcher()

    encoded = matcher._encode(["总胆固醇"])

    assert encoded.shape == (1, 3)


def test_encode_normalized() -> None:
    matcher = build_matcher()

    encoded = matcher._encode(["总胆固醇"])

    assert math.isclose(float(np.linalg.norm(encoded[0])), 1.0, rel_tol=1e-6)


def test_build_index_total() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")

    matcher.build_index(manager)

    assert matcher.index is not None
    assert matcher.index.ntotal > len(manager.standard_dict)


def test_search_exact_name() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)

    results = matcher.search("总胆固醇")

    assert results[0]["standard_code"] == "HY-BZ-001"
    assert results[0]["standard_name"] == "总胆固醇"
    assert results[0]["score"] > 0.9


def test_search_synonym() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)

    results = matcher.search("谷丙转氨酶")

    assert results[0]["standard_code"] == "HY-GG-001"
    assert results[0]["standard_name"] == "丙氨酸氨基转移酶"


def test_search_abbreviation() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)

    results = matcher.search("TC")

    assert results[0]["standard_code"] == "HY-BZ-001"
    assert results[0]["matched_text"] in {"TC", "总胆固醇", "胆固醇", "CHOL"}


def test_search_dedup_same_code() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)

    results = matcher.search("总胆固醇", top_k=5)
    codes = [result["standard_code"] for result in results]

    assert len(codes) == len(set(codes))


def test_search_top_k() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)

    results = matcher.search("总胆固醇", top_k=3)

    assert len(results) <= 3


def test_save_and_load_index(tmp_path: Path) -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)
    matcher.save_index(str(tmp_path))

    reloaded = build_matcher()
    reloaded.load_index(str(tmp_path))

    assert reloaded.is_index_loaded() is True
    assert reloaded.search("总胆固醇")[0]["standard_code"] == "HY-BZ-001"


def test_search_batch() -> None:
    matcher = build_matcher()
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    matcher.build_index(manager)

    results = matcher.search_batch(["总胆固醇", "谷丙转氨酶"], top_k=2)

    assert len(results) == 2
    assert results[0][0]["standard_code"] == "HY-BZ-001"
    assert results[1][0]["standard_code"] == "HY-GG-001"
