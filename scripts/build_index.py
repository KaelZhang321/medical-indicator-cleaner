from __future__ import annotations

import argparse
import json
import pickle
import subprocess
import sys
from pathlib import Path

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from src.dict_manager import DictManager
from src.utils import load_config


def _collect_texts(dict_manager: DictManager) -> tuple[list[str], list[str]]:
    """Gather all texts and their standard_code labels for encoding."""
    texts: list[str] = []
    labels: list[str] = []
    for row in dict_manager.standard_dict.itertuples(index=False):
        candidates = [row.standard_name]
        if row.abbreviation:
            candidates.append(row.abbreviation)
        candidates.extend([a for a in str(row.aliases).split(";") if a.strip()])
        for text in candidates:
            normalized = str(text).strip()
            if normalized:
                texts.append(normalized)
                labels.append(row.code)
    return texts, labels


def _encode_in_subprocess(texts: list[str], model_name: str, cache_dir: str, tmp_dir: Path) -> Path:
    """Encode texts in a separate process to avoid faiss+pytorch segfault on arm64."""
    texts_path = tmp_dir / "texts.json"
    vectors_path = tmp_dir / "vectors.npy"
    texts_path.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")

    encode_script = f"""
import json, numpy as np, sys
from sentence_transformers import SentenceTransformer

texts = json.loads(open("{texts_path}", encoding="utf-8").read())
print(f"Encoding {{len(texts)}} texts...", file=sys.stderr)
model = SentenceTransformer("{model_name}", device="cpu", cache_folder="{cache_dir}")
vectors = model.encode(texts, normalize_embeddings=False, batch_size=128, show_progress_bar=True)
vectors = np.asarray(vectors, dtype=np.float32)
norms = np.linalg.norm(vectors, axis=1, keepdims=True)
norms[norms == 0] = 1.0
vectors = vectors / norms
np.save("{vectors_path}", vectors)
print(f"Saved vectors: shape={{vectors.shape}}", file=sys.stderr)
"""
    print("Step 1/2: Encoding texts in subprocess (avoids faiss+pytorch arm64 conflict)...")
    result = subprocess.run(
        [sys.executable, "-c", encode_script],
        capture_output=False,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Encoding subprocess failed with exit code {result.returncode}")
    return vectors_path


def _build_faiss_index(vectors_path: Path, labels: list[str], texts: list[str],
                       code_to_info: dict, index_dir: str) -> None:
    """Build and save FAISS index from pre-computed vectors."""
    import faiss
    import numpy as np

    print("Step 2/2: Building FAISS index...")
    vectors = np.load(str(vectors_path))
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    target = Path(index_dir)
    target.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(target / "faiss.index"))
    metadata = {"labels": labels, "names": texts, "code_to_info": code_to_info}
    with (target / "metadata.pkl").open("wb") as f:
        pickle.dump(metadata, f)

    print(f"总标准项数: {len(code_to_info)}")
    print(f"总向量数: {index.ntotal}")
    print(f"索引文件: {target / 'faiss.index'}")
    print(f"索引大小(bytes): {(target / 'faiss.index').stat().st_size}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS index for medical indicator normalization.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config file.")
    args = parser.parse_args()

    config = load_config(args.config)
    dict_manager = DictManager(
        config["data"]["standard_dict"],
        config["data"]["alias_dict"],
    )

    texts, labels = _collect_texts(dict_manager)
    code_to_info = {
        row.code: {"standard_name": row.standard_name, "category": row.category}
        for row in dict_manager.standard_dict.itertuples(index=False)
    }
    print(f"Collected {len(texts)} texts from {len(code_to_info)} indicators")

    tmp_dir = Path(config["index"]["path"]) / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    vectors_path = _encode_in_subprocess(
        texts,
        model_name=config["model"]["name"],
        cache_dir=config["model"].get("cache_dir", "./models"),
        tmp_dir=tmp_dir,
    )
    _build_faiss_index(vectors_path, labels, texts, code_to_info, config["index"]["path"])

    # Cleanup temp files
    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()
    print("DONE")


if __name__ == "__main__":
    main()
