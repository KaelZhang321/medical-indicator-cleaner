from __future__ import annotations

import argparse
import os

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from src.pipeline import StandardizationPipeline


def _run_file(args: argparse.Namespace) -> None:
    """Run pipeline from a local JSON/CSV file or directory."""
    pipeline = StandardizationPipeline(config_path=args.config, output_dir=args.output)
    pipeline.run(args.input, output_dir=args.output)
    print(f"输出目录: {args.output or pipeline.output_dir}")


def _run_db(args: argparse.Namespace) -> None:
    """Run pipeline from the HIS production database."""
    from src.db_connector import DBConnector
    from src.db_data_source import DBDataSource
    from src.utils import load_config

    config = load_config(args.config)
    db = DBConnector(config)
    ds = DBDataSource(db)

    if args.study_id:
        dataframe = ds.query_by_study_id(args.study_id)
        label = f"study_id={args.study_id}"
    elif args.patient:
        frames = ds.query_by_patient(args.patient)
        if not frames:
            print("未找到该患者的体检数据")
            db.close()
            return
        import pandas as pd
        dataframe = pd.concat(frames, ignore_index=True)
        label = f"patient={args.patient[:4]}****"
    elif args.date_from and args.date_to:
        dataframe = ds.query_by_date_range(args.date_from, args.date_to, limit=args.limit)
        label = f"date={args.date_from}~{args.date_to}"
    else:
        print("数据库模式需要指定 --study-id, --patient, 或 --date-from/--date-to")
        db.close()
        return

    if dataframe.empty:
        print(f"查询无结果: {label}")
        db.close()
        return

    print(f"查询到 {len(dataframe)} 条数据 ({label})")

    # Feed the DB dataframe through the pipeline's standardization + review
    pipeline = StandardizationPipeline(config_path=args.config, output_dir=args.output)
    results = pipeline._standardize_dataframe(dataframe)
    results = pipeline.ai_reviewer.review(results)
    classified = pipeline.reviewer.classify(results)
    output_dir = args.output or pipeline.output_dir
    pipeline.reviewer.export_csv(classified, output_dir)
    pipeline._print_report(classified)
    print(f"输出目录: {output_dir}")

    db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run medical indicator standardization.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config file.")
    parser.add_argument("--output", default=None, help="Output directory. Defaults to config data.output_dir.")

    subparsers = parser.add_subparsers(dest="source", help="Data source")

    # File mode (default, backwards compatible)
    file_parser = subparsers.add_parser("file", help="Read from local JSON/CSV file")
    file_parser.add_argument("--input", required=True, help="Input JSON/CSV file or directory")

    # Database mode
    db_parser = subparsers.add_parser("db", help="Read from HIS production database")
    db_group = db_parser.add_mutually_exclusive_group()
    db_group.add_argument("--study-id", help="Query single visit by StudyID")
    db_group.add_argument("--patient", help="Query all visits by patient ID card (SFZH)")
    db_parser.add_argument("--date-from", help="Start date for range query (YYYY-MM-DD)")
    db_parser.add_argument("--date-to", help="End date for range query (YYYY-MM-DD)")
    db_parser.add_argument("--limit", type=int, default=10000, help="Max rows for date range query")

    args = parser.parse_args()

    # Backwards compatibility: if no subcommand, check for --input
    if args.source is None:
        # Re-parse with legacy mode
        parser.add_argument("--input", help="Input JSON/CSV file or directory (legacy mode)")
        args = parser.parse_args()
        if hasattr(args, "input") and args.input:
            _run_file(args)
        else:
            parser.print_help()
        return

    if args.source == "file":
        _run_file(args)
    elif args.source == "db":
        _run_db(args)


if __name__ == "__main__":
    main()
