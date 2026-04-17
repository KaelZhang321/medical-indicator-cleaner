from __future__ import annotations

import argparse
from pathlib import Path

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from src.dict_manager import DictManager
from src.l2_embedding_matcher import L2EmbeddingMatcher
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS index for medical indicator normalization.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config file.")
    args = parser.parse_args()

    config = load_config(args.config)
    dict_manager = DictManager(
        config["data"]["standard_dict"],
        config["data"]["alias_dict"],
    )
    matcher = L2EmbeddingMatcher(
        model_name=config["model"]["name"],
        device=config["model"].get("device", "cpu"),
        cache_dir=config["model"].get("cache_dir", "./models"),
    )
    matcher.build_index(dict_manager)
    matcher.save_index(config["index"]["path"])

    index_path = Path(config["index"]["path"]) / "faiss.index"
    print(f"总标准项数: {len(dict_manager.standard_dict)}")
    print(f"总向量数: {matcher.index.ntotal}")
    print(f"索引文件: {index_path}")
    print(f"索引大小(bytes): {index_path.stat().st_size}")


if __name__ == "__main__":
    main()
