#!/usr/bin/env python3
"""Synchronize dictionaries from HIS production database and rebuild FAISS index."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from src.db_connector import DBConnector
from src.db_dict_sync import DictSyncer
from src.utils import load_config, setup_logger

logger = setup_logger("sync_dict")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync dictionaries from HIS DB and rebuild FAISS index.")
    parser.add_argument("--config", default="config/settings.yaml", help="Config file path")
    parser.add_argument("--skip-index", action="store_true", help="Skip FAISS index rebuild")
    parser.add_argument("--only", choices=["standard", "major", "ref", "all"], default="all",
                        help="Which dictionary to sync (default: all)")
    args = parser.parse_args()

    config = load_config(args.config)
    db = DBConnector(config)
    syncer = DictSyncer(db)

    try:
        if args.only in ("all", "standard"):
            print("=== 同步细项字典 (jcmxx → standard_dict.csv) ===")
            std = syncer.sync_standard_dict(config["data"]["standard_dict"])
            print(f"  完成: {len(std)} 条指标")

        if args.only in ("all", "major"):
            print("\n=== 同步大项字典 (sfxm → major_item_dict.csv) ===")
            major = syncer.sync_major_item_dict(config["data"].get("major_item_dict", "data/major_item_dict.csv"))
            print(f"  完成: {len(major)} 条大项")

        if args.only in ("all", "ref"):
            print("\n=== 同步参考范围 (hyb → reference_range_standard.csv) ===")
            ref = syncer.sync_reference_ranges(
                config["data"].get("reference_range_standard", "data/reference_range_standard.csv")
            )
            print(f"  完成: {len(ref)} 条参考范围")

    finally:
        db.close()

    if args.skip_index:
        print("\n跳过 FAISS 索引重建 (--skip-index)")
        return

    print("\n=== 重建 FAISS 索引 ===")
    result = subprocess.run(
        [sys.executable, "scripts/build_index.py", "--config", args.config],
        timeout=600,
    )
    if result.returncode != 0:
        logger.error("FAISS index build failed with exit code %d", result.returncode)
        sys.exit(1)

    print("\n========= 字典同步完成 =========")
    print("下次运行 pipeline 将使用最新字典和索引")


if __name__ == "__main__":
    main()
