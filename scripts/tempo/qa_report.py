#!/usr/bin/env python3
"""Generate QA reports for refine/gold parquet."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import duckdb

from _config import CONFIG_PATH, ensure_output_dirs, load_config


def _profile_parquet(con: duckdb.DuckDBPyConnection, path: Path) -> dict:
    rel = path.as_posix()
    row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{rel}')").fetchone()[0]
    columns = [row[0] for row in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{rel}')").fetchall()]
    null_checks = {}
    for column in columns[:20]:
        null_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{rel}') WHERE \"{column}\" IS NULL OR CAST(\"{column}\" AS VARCHAR) = ''"
        ).fetchone()[0]
        null_checks[column] = int(null_count)
    return {
        "file": path.name,
        "rows": int(row_count),
        "columns": columns,
        "null_counts_sample": null_checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Tempo QA report")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--layer", choices=("refine", "gold", "both"), default="both")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    paths = ensure_output_dirs(config)
    qa_dir = paths["qa"]

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "refine": [], "gold": []}
    con = duckdb.connect()
    try:
        if args.layer in ("refine", "both"):
            for path in sorted(paths["refine"].glob("*.parquet")):
                report["refine"].append(_profile_parquet(con, path))
        if args.layer in ("gold", "both"):
            for path in sorted(paths["gold"].glob("*.parquet")):
                report["gold"].append(_profile_parquet(con, path))
    finally:
        con.close()

    out = qa_dir / "row_counts.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"QA report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
