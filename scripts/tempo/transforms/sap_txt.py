from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
import re

import pandas as pd

from .column_map import normalize_columns

NUMERIC_COLUMNS = {
    "bill_qty",
    "bill_val",
    "cn_amt",
    "cn_qty",
    "do_amt",
    "do_qty",
    "po_amt",
    "po_qty",
    "net_sales",
    "nsp",
    "zcost",
    "zdis_d8",
    "lead_time",
    "stok_akhir",
    "consignment_stock",
    "total_stock",
    "stock_value",
}


def _is_numeric_column(name: str) -> bool:
    return (
        name in NUMERIC_COLUMNS
        or name.startswith("dis")
        or name.startswith("ziokf")
        or bool(re.fullmatch(r"(cnsstck|totstck|valstck)(_\d+)?", name))
        or name.endswith(("stck", "stock_qty", "stock_val"))
    )


def _parse_sap_number(series: pd.Series) -> pd.Series:
    normalized = (
        series.astype("string")
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(normalized, errors="coerce")


def clean_sap_frame(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    df = normalize_columns(df)

    empty_columns = [
        column
        for column in df.columns
        if column.startswith("unnamed") and df[column].fillna("").astype(str).str.strip().eq("").all()
    ]
    if empty_columns:
        df = df.drop(columns=empty_columns)

    for column in df.columns:
        if _is_numeric_column(column):
            df[column] = _parse_sap_number(df[column])
        else:
            df[column] = df[column].astype("string").str.strip()

    for column in ("calmonth", "calmonth2", "calyear"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

    df["_source_file"] = source_file
    df["_loaded_at"] = datetime.now(timezone.utc).isoformat()
    return df


def read_sap_txt(
    path: Path,
    *,
    skip_header_rows: int = 3,
    delimiter: str = "\t",
    encoding: str = "utf-8",
) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=delimiter,
        skiprows=skip_header_rows,
        encoding=encoding,
        dtype=str,
        low_memory=False,
    )
    return clean_sap_frame(df, path.name)


def iter_sap_txt_chunks(
    path: Path,
    *,
    skip_header_rows: int = 3,
    delimiter: str = "\t",
    encoding: str = "utf-8",
    chunk_size: int = 100_000,
) -> Iterator[pd.DataFrame]:
    reader = pd.read_csv(
        path,
        sep=delimiter,
        skiprows=skip_header_rows,
        encoding=encoding,
        dtype=str,
        chunksize=chunk_size,
        low_memory=False,
    )
    for chunk in reader:
        yield clean_sap_frame(chunk, path.name)
