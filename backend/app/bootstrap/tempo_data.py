from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "projects" / "tempo_scan" / "fixtures"
APPROVED_TABLES = {"commercial_sales_daily", "commercial_inventory_daily"}


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[tuple[str, str], ...]
    required: tuple[str, ...]
    date_column: str


SALES_SPEC = TableSpec(
    name="commercial_sales_daily",
    columns=(
        ("sales_date", "DATE"), ("region_name", "VARCHAR"), ("province", "VARCHAR"),
        ("city", "VARCHAR"), ("product_id", "VARCHAR"), ("product_name", "VARCHAR"),
        ("product_category", "VARCHAR"), ("brand", "VARCHAR"), ("outlet_id", "VARCHAR"),
        ("outlet_name", "VARCHAR"), ("outlet_type", "VARCHAR"), ("channel_id", "VARCHAR"),
        ("channel_name", "VARCHAR"), ("customer_segment", "VARCHAR"), ("sales_amount", "DOUBLE"),
        ("sales_qty", "BIGINT"), ("transaction_count", "BIGINT"), ("avg_selling_price", "DOUBLE"),
    ),
    required=("sales_date", "region_name", "product_id", "outlet_id", "channel_id", "sales_amount"),
    date_column="sales_date",
)
INVENTORY_SPEC = TableSpec(
    name="commercial_inventory_daily",
    columns=(
        ("inventory_date", "DATE"), ("product_id", "VARCHAR"), ("product_name", "VARCHAR"),
        ("product_category", "VARCHAR"), ("outlet_id", "VARCHAR"), ("outlet_name", "VARCHAR"),
        ("region_name", "VARCHAR"), ("city", "VARCHAR"), ("opening_stock", "BIGINT"),
        ("closing_stock", "BIGINT"), ("available_stock", "BIGINT"), ("stockout_flag", "BIGINT"),
        ("days_of_supply", "DOUBLE"),
    ),
    required=("inventory_date", "product_id", "outlet_id", "region_name", "available_stock"),
    date_column="inventory_date",
)


def _coerce(value: str, sql_type: str) -> Any:
    if sql_type == "DATE":
        return date.fromisoformat(value)
    if sql_type == "BIGINT":
        return int(value)
    if sql_type == "DOUBLE":
        return float(value)
    return value


def _read(spec: TableSpec) -> tuple[dict[str, Any], ...]:
    path = FIXTURES / f"{spec.name}.csv"
    types = dict(spec.columns)
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(
            {name: _coerce(raw[name], sql_type) for name, sql_type in spec.columns}
            for raw in csv.DictReader(handle)
        )


@dataclass(frozen=True)
class TempoFixtureBundle:
    sales_rows: tuple[dict[str, Any], ...]
    inventory_rows: tuple[dict[str, Any], ...]
    fingerprint: str

    @property
    def sales_columns(self) -> tuple[str, ...]:
        return tuple(name for name, _ in SALES_SPEC.columns)

    @property
    def inventory_columns(self) -> tuple[str, ...]:
        return tuple(name for name, _ in INVENTORY_SPEC.columns)

    def ddl(self, catalog: str, schema: str) -> list[str]:
        return [
            f"CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{spec.name} ("
            + ", ".join(f"{name} {sql_type}" for name, sql_type in spec.columns)
            + ")"
            for spec in (SALES_SPEC, INVENTORY_SPEC)
        ]


def load_tempo_fixture_bundle(limit: int | None = None) -> TempoFixtureBundle:
    sales = _read(SALES_SPEC)
    inventory = _read(INVENTORY_SPEC)
    if limit is not None:
        sales, inventory = sales[:limit], inventory[:limit]
    encoded = json.dumps(
        {"sales": sales, "inventory": inventory},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode()
    return TempoFixtureBundle(sales, inventory, hashlib.sha256(encoded).hexdigest())


@dataclass(frozen=True)
class HeroMetrics:
    current_sales: float
    previous_sales: float
    decline_pct: float
    modern_trade_sales: float
    worst_product: str
    worst_product_change: float


def hero_metrics(rows: tuple[dict[str, Any], ...]) -> HeroMetrics:
    def in_month(row, month: int) -> bool:
        return row["sales_date"].year == 2024 and row["sales_date"].month == month

    west_java = [row for row in rows if row["region_name"] == "Jawa Barat"]
    current = sum(row["sales_amount"] for row in west_java if in_month(row, 3))
    previous = sum(row["sales_amount"] for row in west_java if in_month(row, 2))
    modern = sum(row["sales_amount"] for row in west_java if in_month(row, 3) and row["channel_name"] == "Modern Trade")
    changes: dict[str, float] = {}
    for product in {row["product_name"] for row in west_java}:
        product_rows = [row for row in west_java if row["product_name"] == product]
        changes[product] = sum(row["sales_amount"] for row in product_rows if in_month(row, 3)) - sum(
            row["sales_amount"] for row in product_rows if in_month(row, 2)
        )
    worst_product = min(changes, key=changes.get)
    return HeroMetrics(
        current_sales=current,
        previous_sales=previous,
        decline_pct=((current - previous) * 100 / previous),
        modern_trade_sales=modern,
        worst_product=worst_product,
        worst_product_change=changes[worst_product],
    )
