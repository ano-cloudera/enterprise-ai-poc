#!/usr/bin/env python3
"""Export CSV samples from refine parquet for human review."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pandas as pd

from _config import CONFIG_PATH, ensure_output_dirs, load_config
from parquet_io import read_parquet_limit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export CSV samples from refine parquet")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    paths = ensure_output_dirs(config)
    refine_dir = paths["refine"]
    csv_dir = paths["csv_sample"]
    max_rows = args.max_rows or int(config.get("csv_sample", {}).get("max_rows", 1000))

    count = 0
    for parquet_path in sorted(refine_dir.glob("*.parquet")):
        df = read_parquet_limit(parquet_path, max_rows)
        csv_path = csv_dir / f"{parquet_path.stem}_sample.csv"
        df.to_csv(csv_path, index=False)
        print(f"  → {csv_path.name} ({len(df)} rows)")
        count += 1

    if count == 0:
        print("No refine parquet found. Run refine.py first.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
