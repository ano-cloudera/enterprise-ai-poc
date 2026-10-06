#!/usr/bin/env python3
"""Create DuckDB silver sample for all 9 TEMPO domains (synthetic + optional parquet import)."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402


def _months() -> list[int]:
    return [202410, 202411, 202412]


def _seed_sales() -> pd.DataFrame:
    rows = []
    materials = [f"500-21-0{i}" for i in range(5)] + [f"908-03-1{i}" for i in range(5)]
    for calmonth in _months():
        for idx, material in enumerate(materials):
            rows.append(
                {
                    "calmonth": calmonth,
                    "material": material,
                    "customer": f"C{1000 + idx}",
                    "sales_office": f"SO{(idx % 4) + 1:02d}",
                    "sell_in_bill_val": 1_000_000 * (10 - idx) * (1 + calmonth % 3),
                    "sell_in_bill_qty": 100 * (10 - idx),
                }
            )
    return pd.DataFrame(rows)


def _seed_b2b() -> pd.DataFrame:
    rows = []
    for calmonth in _months():
        for idx, branch in enumerate(["0201", "0202", "0301", "0401"]):
            rows.append(
                {
                    "calmonth": calmonth,
                    "branch": branch,
                    "kode_plu": f"PLU{idx + 1:04d}",
                    "material": f"500-21-0{idx % 5}",
                    "sell_out_bill_val": 500_000 * (idx + 1),
                    "sell_out_bill_qty": 50 * (idx + 1),
                }
            )
    return pd.DataFrame(rows)


def _seed_stock_tempo() -> pd.DataFrame:
    rows = []
    for calmonth in _months():
        for idx in range(8):
            rows.append(
                {
                    "calmonth": calmonth,
                    "material": f"500-21-0{idx % 5}",
                    "warehouse_stock_qty": 1000 - idx * 50,
                    "warehouse_stock_val": (1000 - idx * 50) * 1200,
                }
            )
    return pd.DataFrame(rows)


def _seed_service_level() -> pd.DataFrame:
    rows = []
    for calmonth in _months():
        for idx in range(10):
            po = 100 + idx * 5
            do = max(0, po - idx * 8)
            rows.append(
                {
                    "calmonth": calmonth,
                    "material": f"055-03-0{idx % 3}" if idx < 3 else f"500-21-0{idx % 5}",
                    "service_po_qty": po,
                    "service_do_qty": do,
                    "service_fill_rate": do / po if po else 0,
                    "sell_in_bill_qty": 200 - idx * 10,
                    "sell_in_bill_val": (200 - idx * 10) * 5000,
                }
            )
    return pd.DataFrame(rows)


def _seed_picking() -> pd.DataFrame:
    rows = []
    for period in ["OCT", "NOV", "DEC"]:
        for idx, office in enumerate(["SO01", "SO02", "SO03", "SO04"]):
            rows.append(
                {
                    "reporting_period": period,
                    "sales_office": office,
                    "picking_minutes": 12.5 + idx * 2.1,
                    "picking_accuracy_pct": 0.97 - idx * 0.02,
                }
            )
    return pd.DataFrame(rows)


def _seed_unloading() -> pd.DataFrame:
    rows = []
    for period in ["OCT", "NOV", "DEC"]:
        for idx, office in enumerate(["SO01", "SO02", "SO03"]):
            rows.append(
                {
                    "reporting_period": period,
                    "sales_office": office,
                    "unloading_minutes": 25.0 + idx * 3.5,
                }
            )
    return pd.DataFrame(rows)


def _seed_sat_stock() -> pd.DataFrame:
    rows = []
    for thn, bln in [(2024, "OCT"), (2024, "NOV"), (2024, "DEC")]:
        for idx in range(6):
            rows.append(
                {
                    "thn": thn,
                    "bln": bln,
                    "division": f"DIV{(idx % 3) + 1}",
                    "plu": f"{1000 + idx}",
                    "dc_stock_qty": 500 - idx * 20,
                    "store_stock_qty": 200 - idx * 10,
                }
            )
    return pd.DataFrame(rows)


def _seed_sat_oos() -> pd.DataFrame:
    rows = []
    for calmonth in _months():
        for idx in range(8):
            rows.append(
                {
                    "calmonth": calmonth,
                    "material_code": f"908-03-1{idx % 5}",
                    "cust_id": f"T{2000 + idx}",
                    "oos_flag": idx % 3 == 0,
                }
            )
    return pd.DataFrame(rows)


def _seed_sat_promo() -> pd.DataFrame:
    rows = []
    for idx in range(20):
        rows.append(
            {
                "calmonth": 202412,
                "material": f"500-21-0{idx % 5}",
                "promo_mechanism": "DISCOUNT" if idx % 2 == 0 else "BUNDLE",
                "observed_uplift_val": 100_000 + idx * 5000,
            }
        )
    return pd.DataFrame(rows)


TABLES: dict[str, tuple[str, callable]] = {
    "sales_oct_dec_2024": ("sales_oct_dec_2024", _seed_sales),
    "b2b_oct_dec_2024": ("b2b_oct_dec_2024", _seed_b2b),
    "stock_tempo_oct_dec_2024": ("stock_tempo_oct_dec_2024", _seed_stock_tempo),
    "service_level_oct_dec_2024": ("service_level_oct_dec_2024", _seed_service_level),
    "picking_okt_des_24": ("picking_okt_des_24", _seed_picking),
    "unloading_okt_des_24": ("unloading_okt_des_24", _seed_unloading),
    "stock_sat_idm_monthly_okt_des_24": ("stock_sat_idm_monthly_okt_des_24", _seed_sat_stock),
    "sat_oos_okt_des_2024": ("sat_oos_okt_des_2024", _seed_sat_oos),
    "sat_promo_des_24": ("sat_promo_des_24", _seed_sat_promo),
}


def _try_load_parquet(parquet_dir: Path, table_name: str) -> pd.DataFrame | None:
    for candidate in (
        parquet_dir / f"{table_name}.parquet",
        parquet_dir / table_name / "data.parquet",
    ):
        if candidate.exists():
            return pd.read_parquet(candidate)
    return None


def main() -> None:
    settings = get_settings()
    db_path = settings.duckdb_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")

    for table_name, (_, factory) in TABLES.items():
        df = _try_load_parquet(settings.parquet_sample_dir, table_name)
        if df is None:
            df = factory()
        con.register("_df", df)
        con.execute(f'CREATE TABLE silver."{table_name}" AS SELECT * FROM _df')
        con.unregister("_df")
        count = con.execute(f'SELECT COUNT(*) FROM silver."{table_name}"').fetchone()[0]
        print(f"  silver.{table_name}: {count:,} rows")

    con.close()
    print(f"DuckDB ready: {db_path}")


if __name__ == "__main__":
    main()
