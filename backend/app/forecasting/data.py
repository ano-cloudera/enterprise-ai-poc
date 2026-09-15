from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from app.forecasting.models import MonthlySales


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "projects" / "tempo_scan" / "fixtures"


def _month(value: str) -> date:
    parsed = date.fromisoformat(value)
    return parsed.replace(day=1)


def load_monthly_sales() -> list[MonthlySales]:
    combined: dict[tuple[date, str, str, str], float] = defaultdict(float)
    history_path = FIXTURES / "commercial_sales_monthly_history.csv"
    if not history_path.exists():
        raise FileNotFoundError("Forecast history fixture missing. Run scripts/generate_sample_data.py")
    with history_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (_month(row["sales_month"]), row["region_name"], row["product_name"], row["channel_name"])
            combined[key] += float(row["sales_amount"])
    with (FIXTURES / "commercial_sales_daily.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (_month(row["sales_date"]), row["region_name"], row["product_name"], row["channel_name"])
            combined[key] += float(row["sales_amount"])
    return [
        MonthlySales(month=month, region_name=region, product_name=product, channel_name=channel, sales_amount=amount)
        for (month, region, product, channel), amount in sorted(combined.items())
    ]


def supported_series(rows: list[MonthlySales]) -> list[MonthlySales]:
    values: dict[tuple[str, str, date], float] = defaultdict(float)
    for row in rows:
        values[("total", "ALL", row.month)] += row.sales_amount
        values[("region", row.region_name or "", row.month)] += row.sales_amount
        values[("product", row.product_name or "", row.month)] += row.sales_amount
        values[("channel", row.channel_name or "", row.month)] += row.sales_amount
    return [
        MonthlySales(month=month, dimension_type=dimension_type, dimension_value=dimension_value, sales_amount=amount)
        for (dimension_type, dimension_value, month), amount in sorted(values.items())
    ]
