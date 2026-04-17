#!/usr/bin/env python3
"""One-shot CLI to enrich data assets via LLM generation + web crawling."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Bootstrap project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd

from scripts.data_enrichment.merger import DataMerger
from src.utils import load_config, setup_logger

logger = setup_logger("run_enrichment")


def run_llm(config: dict, enrichment_dir: Path) -> None:
    """Step 1: Generate data via LLM API."""
    from scripts.data_enrichment.llm_generator import LLMGenerator

    standard_dict = pd.read_csv(config["data"]["standard_dict"], dtype=str).fillna("")
    gen = LLMGenerator(model=config.get("ai_review", {}).get("model", "doubao-seed-2-0-pro-260215"))

    logger.info("=== LLM: Generating aliases ===")
    gen.generate_aliases(standard_dict, str(enrichment_dir / "llm_aliases.json"))

    logger.info("=== LLM: Generating reference ranges ===")
    gen.generate_reference_ranges(standard_dict, str(enrichment_dir / "llm_reference_ranges.json"))

    logger.info("=== LLM: Generating risk weights ===")
    gen.generate_risk_weights(standard_dict, str(enrichment_dir / "llm_risk_weights.json"))

    logger.info("=== LLM: Generating new indicators ===")
    existing_codes = set(standard_dict["code"].tolist())
    gen.generate_new_indicators(existing_codes, str(enrichment_dir / "llm_new_indicators.json"))


def run_crawl(config: dict, enrichment_dir: Path) -> None:
    """Step 2: Crawl public sources for verification."""
    from scripts.data_enrichment.crawler_baike import BaikeCrawler
    from scripts.data_enrichment.crawler_dxy import DxyCrawler

    standard_dict = pd.read_csv(config["data"]["standard_dict"], dtype=str).fillna("")
    names = standard_dict["standard_name"].tolist()

    logger.info("=== Crawl: DXY lab-test encyclopedia ===")
    dxy = DxyCrawler(cache_dir=str(enrichment_dir / "cache_dxy"))
    dxy.crawl_all(names, str(enrichment_dir / "crawled_dxy.json"))

    logger.info("=== Crawl: Baidu Baike ===")
    baike = BaikeCrawler(cache_dir=str(enrichment_dir / "cache_baike"))
    baike.crawl_all(names, str(enrichment_dir / "crawled_baike.json"))


def run_merge(config: dict, enrichment_dir: Path) -> None:
    """Step 3: Merge all sources and write to CSV."""
    merger = DataMerger()

    standard_dict = pd.read_csv(config["data"]["standard_dict"], dtype=str).fillna("")

    # --- Aliases ---
    llm_aliases = merger.load_json(str(enrichment_dir / "llm_aliases.json"))
    if not isinstance(llm_aliases, dict):
        llm_aliases = {}

    # Build crawled aliases index: standard_name → aliases list
    crawled_dxy = merger.load_json(str(enrichment_dir / "crawled_dxy.json"))
    crawled_baike = merger.load_json(str(enrichment_dir / "crawled_baike.json"))
    if not isinstance(crawled_dxy, list):
        crawled_dxy = []
    if not isinstance(crawled_baike, list):
        crawled_baike = []

    # Map crawled results back to standard_code via name matching
    name_to_code = {row.standard_name: row.code for row in standard_dict.itertuples(index=False)}
    crawled_aliases: dict[str, list[str]] = {}
    for item in crawled_dxy:
        code = name_to_code.get(item.get("query_name", ""), "")
        if code:
            aliases = item.get("aliases", [])
            en = item.get("english_name", "")
            abbr = item.get("abbreviation", "")
            all_names = aliases + ([en] if en else []) + ([abbr] if abbr else [])
            crawled_aliases.setdefault(code, []).extend(all_names)
    for item in crawled_baike:
        code = name_to_code.get(item.get("query_name", ""), "")
        if code:
            aliases = item.get("aliases", [])
            en = item.get("english_name", "")
            all_names = aliases + ([en] if en else [])
            crawled_aliases.setdefault(code, []).extend(all_names)

    logger.info("=== Merge: Aliases ===")
    updated_dict = merger.merge_aliases(standard_dict, llm_aliases, crawled_aliases)

    # --- New indicators ---
    llm_new = merger.load_json(str(enrichment_dir / "llm_new_indicators.json"))
    if not isinstance(llm_new, list):
        llm_new = []
    if llm_new:
        logger.info("=== Merge: New indicators ===")
        updated_dict = merger.merge_new_indicators(llm_new, updated_dict)

    # Validate and save standard_dict
    issues = merger.validate_standard_dict(updated_dict)
    if issues:
        for issue in issues:
            logger.warning("standard_dict issue: %s", issue)
    merger.save_csv(updated_dict, str(enrichment_dir / "review_standard_dict.csv"))

    # --- Reference ranges ---
    logger.info("=== Merge: Reference ranges ===")
    llm_ranges = merger.load_json(str(enrichment_dir / "llm_reference_ranges.json"))
    if not isinstance(llm_ranges, list):
        llm_ranges = []
    crawled_ranges_list: list[dict] = []
    for item in crawled_dxy:
        if item.get("reference_ranges"):
            code = name_to_code.get(item.get("query_name", ""), "")
            if code:
                crawled_ranges_list.append({
                    "standard_code": code,
                    "reference_ranges": item["reference_ranges"],
                })

    ref_existing = pd.read_csv(config["data"].get("reference_range_standard", "data/reference_range_standard.csv"), dtype=str).fillna("")
    # Convert numeric columns
    for col in ["ref_min", "ref_max", "age_min", "age_max"]:
        if col in ref_existing.columns:
            ref_existing[col] = pd.to_numeric(ref_existing[col], errors="coerce")

    ref_merged = merger.merge_reference_ranges(llm_ranges, crawled_ranges_list, ref_existing)
    ref_issues = merger.validate_reference_ranges(ref_merged)
    if ref_issues:
        for issue in ref_issues:
            logger.warning("reference_range issue: %s", issue)
    merger.save_csv(ref_merged, str(enrichment_dir / "review_reference_ranges.csv"))

    # --- Risk weights ---
    logger.info("=== Merge: Risk weights ===")
    llm_weights = merger.load_json(str(enrichment_dir / "llm_risk_weights.json"))
    if not isinstance(llm_weights, list):
        llm_weights = []
    risk_existing = pd.read_csv(config["data"].get("risk_weight", "data/risk_weight.csv"), dtype=str).fillna("")
    risk_merged = merger.merge_risk_weights(llm_weights, risk_existing)
    merger.save_csv(risk_merged, str(enrichment_dir / "review_risk_weights.csv"))

    # --- Summary ---
    print("\n========= 数据补全合并完成 =========")
    print(f"standard_dict:     {len(updated_dict)} 条 → {enrichment_dir / 'review_standard_dict.csv'}")
    print(f"reference_ranges:  {len(ref_merged)} 条 → {enrichment_dir / 'review_reference_ranges.csv'}")
    print(f"risk_weights:      {len(risk_merged)} 条 → {enrichment_dir / 'review_risk_weights.csv'}")
    print("\n请人工审核 review_*.csv 文件后，将确认的数据覆盖到 data/ 目录：")
    print(f"  cp {enrichment_dir}/review_standard_dict.csv data/standard_dict.csv")
    print(f"  cp {enrichment_dir}/review_reference_ranges.csv data/reference_range_standard.csv")
    print(f"  cp {enrichment_dir}/review_risk_weights.csv data/risk_weight.csv")
    print("=================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich medical indicator data assets")
    parser.add_argument("--config", default="config/settings.yaml", help="Config file path")
    parser.add_argument("--output", default="data/enrichment", help="Enrichment output directory")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Run LLM + Crawl + Merge (default)")
    group.add_argument("--llm-only", action="store_true", help="Only run LLM generation")
    group.add_argument("--crawl-only", action="store_true", help="Only run crawlers")
    group.add_argument("--merge-only", action="store_true", help="Only merge existing results")

    args = parser.parse_args()
    config = load_config(args.config)
    enrichment_dir = Path(args.output)
    enrichment_dir.mkdir(parents=True, exist_ok=True)

    if args.llm_only:
        run_llm(config, enrichment_dir)
    elif args.crawl_only:
        run_crawl(config, enrichment_dir)
    elif args.merge_only:
        run_merge(config, enrichment_dir)
    else:
        # Default: all steps
        run_llm(config, enrichment_dir)
        run_crawl(config, enrichment_dir)
        run_merge(config, enrichment_dir)


if __name__ == "__main__":
    main()
