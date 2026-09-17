from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "projects" / "tempo_scan" / "fixtures"
DEFAULT_DUCKDB_PATH = ROOT / "runtime" / "tempo_scan.duckdb"
# Full-replace write boundary (TrinoDemoLoader): DELETE FROM + INSERT INTO
# the whole table on every bootstrap run. Only sales/inventory use this
# semantics. commercial_sales_forecast intentionally stays out of this set
# — it has its own writer (TrinoForecastWriter) that replaces rows scoped
# to one model_version, not the whole table. See EXTENDED_APPROVED_TABLES
# below for the other DuckDB-sourced tables, which get their own
# per-table writer for the same reason.
APPROVED_TABLES = {"commercial_sales_daily", "commercial_inventory_daily"}

# Allowlist for the extended (DuckDB-sourced) write boundary. Each of these
# is replaced in full on every bootstrap run, same as sales/inventory, but
# kept in a separate set so the original APPROVED_TABLES contract (and the
# tests that pin it) stays untouched.
EXTENDED_APPROVED_TABLES = {
    "commercial_product_master",
    "commercial_weather_monthly",
    "commercial_market_monthly",
    "commercial_market_digital_snapshot",
}


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[tuple[str, str], ...]
    required: tuple[str, ...]
    date_column: str | None


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
PRODUCT_MASTER_SPEC = TableSpec(
    name="commercial_product_master",
    columns=(
        ("product_id", "VARCHAR"), ("product_name", "VARCHAR"), ("product_category", "VARCHAR"),
        ("product_categories", "VARCHAR"), ("synthetic", "BOOLEAN"),
    ),
    required=("product_id", "product_name"),
    date_column=None,
)
FORECAST_SPEC = TableSpec(
    name="commercial_sales_forecast",
    columns=(
        ("forecast_date", "DATE"), ("generated_at", "TIMESTAMP"), ("forecast_horizon", "BIGINT"),
        ("forecast_sales", "DOUBLE"), ("lower_bound", "DOUBLE"), ("upper_bound", "DOUBLE"),
        ("model_name", "VARCHAR"), ("model_version", "VARCHAR"), ("training_cutoff_date", "DATE"),
        ("dimension_type", "VARCHAR"), ("dimension_value", "VARCHAR"),
    ),
    required=("forecast_date", "forecast_sales", "model_version"),
    date_column="forecast_date",
)
WEATHER_SPEC = TableSpec(
    name="commercial_weather_monthly",
    columns=(
        ("period", "DATE"), ("region_name", "VARCHAR"), ("weather_location", "VARCHAR"),
        ("avg_temperature_c", "DOUBLE"), ("total_precipitation_mm", "DOUBLE"),
        ("avg_relative_humidity_pct", "DOUBLE"), ("rainy_days", "BIGINT"), ("source", "VARCHAR"),
        ("generated_at", "TIMESTAMP"),
    ),
    required=("period", "region_name"),
    date_column="period",
)
MARKET_MONTHLY_SPEC = TableSpec(
    name="commercial_market_monthly",
    columns=(
        ("period", "DATE"), ("region_name", "VARCHAR"), ("category", "VARCHAR"), ("product_name", "VARCHAR"),
        ("brand", "VARCHAR"), ("manufacturer", "VARCHAR"), ("competitor_group", "VARCHAR"),
        ("estimated_market_value", "DOUBLE"), ("estimated_market_volume", "DOUBLE"),
        ("market_share_pct", "DOUBLE"), ("market_growth_pct", "DOUBLE"), ("avg_market_price", "DOUBLE"),
        ("promo_intensity_index", "DOUBLE"), ("distribution_coverage_pct", "DOUBLE"),
        ("digital_visibility_index", "DOUBLE"), ("competitive_pressure_index", "DOUBLE"),
        ("opportunity_score", "DOUBLE"), ("opportunity_components", "VARCHAR"), ("source_type", "VARCHAR"),
        ("data_confidence", "VARCHAR"), ("generated_at", "TIMESTAMP"), ("price_anchor_source", "VARCHAR"),
        ("price_anchor_method", "VARCHAR"), ("price_anchor_value", "DOUBLE"),
    ),
    required=("period", "region_name", "product_name"),
    date_column="period",
)
MARKET_DIGITAL_SNAPSHOT_SPEC = TableSpec(
    name="commercial_market_digital_snapshot",
    columns=(
        ("observed_at", "TIMESTAMP"), ("query", "VARCHAR"), ("product_name", "VARCHAR"), ("category", "VARCHAR"),
        ("seller", "VARCHAR"), ("title", "VARCHAR"), ("observed_price", "DOUBLE"), ("old_price", "DOUBLE"),
        ("discount_pct", "DOUBLE"), ("rating", "DOUBLE"), ("review_count", "BIGINT"),
        ("search_position", "BIGINT"), ("availability", "VARCHAR"), ("source", "VARCHAR"),
        ("source_type", "VARCHAR"), ("data_confidence", "VARCHAR"), ("package_type", "VARCHAR"),
        ("package_quantity", "BIGINT"), ("unit_type", "VARCHAR"), ("normalized_unit_price", "DOUBLE"),
        ("normalization_confidence", "VARCHAR"),
    ),
    required=("observed_at", "product_name"),
    date_column=None,
)

# Tables sourced from the local governed DuckDB runtime rather than a CSV
# fixture: they are produced by offline jobs (weather fetch, market snapshot
# refresh) that already write into DuckDB directly. commercial_sales_forecast
# is intentionally excluded — it already has a dedicated writer
# (app.forecasting.persistence.TrinoForecastWriter) with its own
# model_version-scoped replace semantics; FORECAST_SPEC is kept here only as
# a column-schema reference, not for this generic full-replace loader.
DUCKDB_SOURCED_SPECS = (
    PRODUCT_MASTER_SPEC, WEATHER_SPEC, MARKET_MONTHLY_SPEC, MARKET_DIGITAL_SNAPSHOT_SPEC,
)


def _coerce(value: str, sql_type: str) -> Any:
    if sql_type == "DATE":
        return date.fromisoformat(value)
    if sql_type == "BIGINT":
        return int(value)
    if sql_type == "DOUBLE":
        return float(value)
    return value


def _duckdb_ddl(spec: TableSpec, catalog: str, schema: str) -> str:
    columns_sql = ", ".join(f"{name} {sql_type}" for name, sql_type in spec.columns)
    return f"CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{spec.name} ({columns_sql}) WITH (format = 'ICEBERG')"


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
        return [_duckdb_ddl(spec, catalog, schema) for spec in (SALES_SPEC, INVENTORY_SPEC)]


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


def _read_duckdb_table(connection, spec: TableSpec) -> tuple[dict[str, Any], ...]:
    """Read a governed table from the local DuckDB runtime, coercing values
    into plain Python types the Trino DBAPI driver can bind directly."""
    columns = [name for name, _ in spec.columns]
    rows = connection.execute(f"SELECT {', '.join(columns)} FROM {spec.name}").fetchall()
    result = []
    for raw_row in rows:
        record: dict[str, Any] = {}
        for (name, sql_type), value in zip(spec.columns, raw_row):
            if value is not None and sql_type == "TIMESTAMP" and isinstance(value, datetime):
                value = value.replace(tzinfo=None)
            record[name] = value
        result.append(record)
    return tuple(result)


@dataclass(frozen=True)
class TempoExtendedBundle:
    """Rows for the DuckDB-sourced tables (forecast, weather, market
    intelligence, product master), read from the local governed runtime
    rather than a CSV fixture. Kept separate from TempoFixtureBundle so the
    proven sales/inventory hero-story bootstrap path is untouched."""

    rows_by_table: dict[str, tuple[dict[str, Any], ...]]

    def columns(self, spec: TableSpec) -> tuple[str, ...]:
        return tuple(name for name, _ in spec.columns)

    def ddl(self, catalog: str, schema: str) -> list[str]:
        return [
            _duckdb_ddl(spec, catalog, schema)
            for spec in DUCKDB_SOURCED_SPECS
            if spec.name in self.rows_by_table
        ]


def load_tempo_extended_bundle(duckdb_path: Path | str = DEFAULT_DUCKDB_PATH) -> TempoExtendedBundle:
    """Load rows for every DuckDB-sourced governed table that has data
    present. A table with zero rows in the local runtime (e.g. forecast not
    yet trained) is simply omitted rather than failing the whole bundle."""
    rows_by_table: dict[str, tuple[dict[str, Any], ...]] = {}
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        for spec in DUCKDB_SOURCED_SPECS:
            if spec.name not in existing_tables:
                continue
            rows_by_table[spec.name] = _read_duckdb_table(connection, spec)
    return TempoExtendedBundle(rows_by_table)


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
