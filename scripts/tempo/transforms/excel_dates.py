from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

EXCEL_EPOCH = datetime(1899, 12, 30)
DATE_COLUMN_CANDIDATES = ("survey_date", "tgl_dcp", "upd_date")


def excel_serial_to_date(value: object) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            serial = int(stripped)
        else:
            parsed = pd.to_datetime(stripped, errors="coerce")
            return None if pd.isna(parsed) else parsed.date().isoformat()
    elif isinstance(value, (int, float)):
        serial = int(value)
    else:
        return value
    return (EXCEL_EPOCH + timedelta(days=serial)).date().isoformat()


def convert_excel_date_columns(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    targets = columns or [col for col in DATE_COLUMN_CANDIDATES if col in df.columns]
    if not targets:
        return df
    out = df.copy()
    for column in targets:
        out[column] = out[column].map(excel_serial_to_date)
    return out
