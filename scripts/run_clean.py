from __future__ import annotations

import argparse

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from src.pipeline import StandardizationPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run medical indicator standardization.")
    parser.add_argument("--input", required=True, help="Input JSON/CSV file or a directory containing JSON files.")
    parser.add_argument("--output", default=None, help="Output directory. Defaults to config data.output_dir.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config file.")
    args = parser.parse_args()

    pipeline = StandardizationPipeline(config_path=args.config, output_dir=args.output)
    pipeline.run(args.input, output_dir=args.output)
    output_dir = args.output or pipeline.output_dir
    print(f"输出目录: {output_dir}")


if __name__ == "__main__":
    main()
