from __future__ import annotations

from pathlib import Path
from collections.abc import Iterable

import duckdb
import pandas as pd


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.register("frame", df)
        con.execute(f"COPY frame TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()


def read_parquet(path: Path) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        return con.execute(f"SELECT * FROM read_parquet('{path.as_posix()}')").df()
    finally:
        con.close()


def read_parquet_limit(path: Path, limit: int) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{path.as_posix()}') LIMIT ?",
            [limit],
        ).df()
    finally:
        con.close()


def combine_parquet(parts: Iterable[Path], output_path: Path) -> None:
    part_paths = [path.as_posix() for path in parts]
    if not part_paths:
        raise ValueError("No parquet parts to combine")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    escaped = ", ".join(f"'{path}'" for path in part_paths)
    con = duckdb.connect()
    try:
        con.execute(
            f"""
            COPY (
                SELECT *
                FROM read_parquet([{escaped}], union_by_name = true)
            )
            TO '{output_path.as_posix()}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
    finally:
        con.close()
