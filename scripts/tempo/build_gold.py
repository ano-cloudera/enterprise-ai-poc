#!/usr/bin/env python3
"""Refine parquet → gold fact/dim tables (scaffold)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import duckdb
import pandas as pd

from _config import CONFIG_PATH, ensure_output_dirs, load_config
from parquet_io import read_parquet, write_parquet


FACT_SOURCES = {
    "fact_sales": ("sales.parquet", "sell_in"),
    "fact_b2b_sales": ("b2b.parquet", "sell_out"),
    "fact_stock": ("stock.parquet", None),
    "fact_service_level": ("service_level.parquet", None),
    "fact_oos": ("oos.parquet", None),
}


def _read_refine(refine_dir: Path, filename: str) -> pd.DataFrame:
    path = refine_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing refine parquet: {path}")
    return read_parquet(path)


def build_facts(refine_dir: Path, gold_dir: Path) -> list[str]:
    written: list[str] = []
    for fact_name, (source_file, channel) in FACT_SOURCES.items():
        df = _read_refine(refine_dir, source_file)
        if channel:
            df = df.copy()
            df["channel"] = channel
        out = gold_dir / f"{fact_name}.parquet"
        write_parquet(df, out)
        written.append(out.name)
        print(f"  → {out.name} ({len(df):,} rows)")
    return written


def build_dims(refine_dir: Path, gold_dir: Path) -> list[str]:
    written: list[str] = []

    # Reference dims copied from refine when available
    for name in ("dim_uom", "dim_key_figure"):
        src = refine_dir / f"{name}.parquet"
        if src.exists():
            df = read_parquet(src)
            out = gold_dir / f"{name}.parquet"
            write_parquet(df, out)
            written.append(out.name)
            print(f"  → {out.name} ({len(df):,} rows)")

    con = duckdb.connect()
    try:
        sales = refine_dir / "sales.parquet"
        b2b = refine_dir / "b2b.parquet"
        stock = refine_dir / "stock.parquet"
        oos = refine_dir / "oos.parquet"

        if sales.exists():
            customer_queries = [
                f"SELECT DISTINCT customer_id FROM read_parquet('{sales.as_posix()}') WHERE customer_id IS NOT NULL"
            ]
            if b2b.exists():
                customer_queries.append(
                    f"SELECT DISTINCT customer_id FROM read_parquet('{b2b.as_posix()}') WHERE customer_id IS NOT NULL"
                )
            if oos.exists():
                customer_queries.append(
                    f"SELECT DISTINCT customer_id FROM read_parquet('{oos.as_posix()}') WHERE customer_id IS NOT NULL"
                )
            dim_customer = con.execute(" UNION ".join(customer_queries)).df()
            out = gold_dir / "dim_customer.parquet"
            write_parquet(dim_customer, out)
            written.append(out.name)
            print(f"  → {out.name} ({len(dim_customer):,} rows)")

            dim_material = con.execute(
                f"""
                SELECT DISTINCT material_id
                FROM read_parquet('{sales.as_posix()}')
                WHERE material_id IS NOT NULL
                """
            ).df()
            if b2b.exists():
                extra = con.execute(
                    f"SELECT DISTINCT material_id FROM read_parquet('{b2b.as_posix()}') WHERE material_id IS NOT NULL"
                ).df()
                dim_material = pd.concat([dim_material, extra]).drop_duplicates()
            if stock.exists():
                extra = con.execute(
                    f"SELECT DISTINCT material_id FROM read_parquet('{stock.as_posix()}') WHERE material_id IS NOT NULL"
                ).df()
                dim_material = pd.concat([dim_material, extra]).drop_duplicates()
            out = gold_dir / "dim_material.parquet"
            write_parquet(dim_material, out)
            written.append(out.name)
            print(f"  → {out.name} ({len(dim_material):,} rows)")

            dim_sales_org = con.execute(
                f"""
                SELECT DISTINCT sales_org, sales_office, sales_group
                FROM read_parquet('{sales.as_posix()}')
                """
            ).df()
            out = gold_dir / "dim_sales_org.parquet"
            write_parquet(dim_sales_org, out)
            written.append(out.name)
            print(f"  → {out.name} ({len(dim_sales_org):,} rows)")

        if stock.exists():
            dim_plant = con.execute(
                f"""
                SELECT DISTINCT plant, stor_loc
                FROM read_parquet('{stock.as_posix()}')
                """
            ).df()
            out = gold_dir / "dim_plant.parquet"
            write_parquet(dim_plant, out)
            written.append(out.name)
            print(f"  → {out.name} ({len(dim_plant):,} rows)")

        dim_time = pd.DataFrame({"calmonth": [202410, 202411, 202412]})
        out = gold_dir / "dim_time.parquet"
        write_parquet(dim_time, out)
        written.append(out.name)
        print(f"  → {out.name} ({len(dim_time):,} rows)")
    finally:
        con.close()

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build gold datamart parquet from refine layer")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    paths = ensure_output_dirs(config)
    refine_dir = paths["refine"]
    gold_dir = paths["gold"]

    if not any(refine_dir.glob("*.parquet")):
        print("ERROR: no refine parquet found. Run refine.py first.", file=sys.stderr)
        return 1

    print("Building facts...")
    build_facts(refine_dir, gold_dir)
    print("Building dims...")
    build_dims(refine_dir, gold_dir)
    print(f"Gold tables written to {gold_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
