from __future__ import annotations

import pandas as pd


def apply_scale_div100(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if not columns:
        return df
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce") / 100
    return out
