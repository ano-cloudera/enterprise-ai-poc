from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Any

import sqlglot
from sqlglot import exp

from app.bootstrap.tempo_data import INVENTORY_SPEC, SALES_SPEC, TempoFixtureBundle, hero_metrics
from app.bootstrap.config import LoaderConfig
from app.bootstrap.loader import _loader_driver_connect
from app.semantic.intent import AnalyticalIntent
from app.semantic.models import SemanticProject
from app.semantic.resolver import normalize_analytical_intent, resolve_analytical_intent
from app.tools.semantic_sql import generate_semantic_sql
from app.tools.sql_validator import validate_readonly_sql


class ValidationFailure(RuntimeError):
    pass


@dataclass
class DemoValidationSnapshot:
    tables: dict[str, dict[str, Any]]
    regions: set[str]
    channels: set[str]
    products: set[str]
    current_sales: float
    previous_sales: float
    modern_trade_sales: float
    worst_product: str
    trend_rows: int


@dataclass(frozen=True)
class DemoValidationReport:
    ok: bool
    hero_scenario: str
    sales_row_count: int
    inventory_row_count: int
    min_date: str
    max_date: str


def validate_snapshot(snapshot: DemoValidationSnapshot, expected: TempoFixtureBundle, tolerance: float = 0.01) -> DemoValidationReport:
    expected_counts = {SALES_SPEC.name: len(expected.sales_rows), INVENTORY_SPEC.name: len(expected.inventory_rows)}
    for spec in (SALES_SPEC, INVENTORY_SPEC):
        actual = snapshot.tables.get(spec.name)
        if not actual or not actual.get("exists"):
            raise ValidationFailure(f"missing table: {spec.name}")
        if actual.get("row_count") != expected_counts[spec.name]:
            raise ValidationFailure(f"row count mismatch: {spec.name}")
        if not {name for name, _ in spec.columns}.issubset(set(actual.get("columns", []))):
            raise ValidationFailure(f"column mismatch: {spec.name}")
        if actual.get("null_required"):
            raise ValidationFailure(f"required null values: {spec.name}")
    expected_hero = hero_metrics(expected.sales_rows)
    if not math.isclose(snapshot.current_sales, expected_hero.current_sales, abs_tol=tolerance) or not math.isclose(snapshot.previous_sales, expected_hero.previous_sales, abs_tol=tolerance):
        raise ValidationFailure("hero metric mismatch")
    if not math.isclose(snapshot.modern_trade_sales, expected_hero.modern_trade_sales, abs_tol=tolerance):
        raise ValidationFailure("hero Modern Trade mismatch")
    if snapshot.worst_product != expected_hero.worst_product:
        raise ValidationFailure("hero product ranking mismatch")
    if snapshot.trend_rows < 3:
        raise ValidationFailure("hero trend mismatch")
    if "Jawa Barat" not in snapshot.regions or "Modern Trade" not in snapshot.channels or "Bodrex Flu & Batuk" not in snapshot.products:
        raise ValidationFailure("hero dimension values missing")
    sales = snapshot.tables[SALES_SPEC.name]
    return DemoValidationReport(
        ok=True,
        hero_scenario="PASS",
        sales_row_count=expected_counts[SALES_SPEC.name],
        inventory_row_count=expected_counts[INVENTORY_SPEC.name],
        min_date=str(sales["min_date"]),
        max_date=str(sales["max_date"]),
    )


@dataclass(frozen=True)
class ParityResult:
    ok: bool
    differences: tuple[str, ...]


def compare_query_rows(duckdb_rows: list[dict[str, Any]], trino_rows: list[dict[str, Any]], tolerance: float = 0.001) -> ParityResult:
    differences: list[str] = []
    if len(duckdb_rows) != len(trino_rows):
        differences.append("row_count")
        return ParityResult(False, tuple(differences))
    for index, (left, right) in enumerate(zip(duckdb_rows, trino_rows)):
        if set(left) != set(right):
            differences.append(f"row_{index}_shape")
            continue
        for key in left:
            left_value, right_value = left[key], right[key]
            if isinstance(left_value, (int, float, Decimal)) and not isinstance(left_value, bool) and isinstance(right_value, (int, float, Decimal)) and not isinstance(right_value, bool):
                equal = math.isclose(float(left_value), float(right_value), abs_tol=tolerance, rel_tol=tolerance)
            else:
                equal = left_value == right_value
            if not equal:
                differences.append(f"row_{index}.{key}")
    return ParityResult(not differences, tuple(differences))


def collect_validation_snapshot(query, catalog: str, schema: str) -> DemoValidationSnapshot:
    """Collect only fixed, project-owned post-load checks through a caller-supplied query function."""
    sales = f"{catalog}.{schema}.{SALES_SPEC.name}"
    inventory = f"{catalog}.{schema}.{INVENTORY_SPEC.name}"
    sales_columns = ", ".join(f"'{name}'" for name, _ in SALES_SPEC.columns)
    inventory_columns = ", ".join(f"'{name}'" for name, _ in INVENTORY_SPEC.columns)
    sales_required = " OR ".join(f"{name} IS NULL" for name in SALES_SPEC.required)
    inventory_required = " OR ".join(f"{name} IS NULL" for name in INVENTORY_SPEC.required)
    statements = {
        "sales_stats": (
            f"SELECT TRUE AS exists, COUNT(*) AS row_count, ARRAY[{sales_columns}] AS columns, "
            f"SUM(CASE WHEN {sales_required} THEN 1 ELSE 0 END) AS null_required, "
            f"MIN(sales_date) AS min_date, MAX(sales_date) AS max_date FROM {sales}"
        ),
        "inventory_stats": (
            f"SELECT TRUE AS exists, COUNT(*) AS row_count, ARRAY[{inventory_columns}] AS columns, "
            f"SUM(CASE WHEN {inventory_required} THEN 1 ELSE 0 END) AS null_required, "
            f"MIN(inventory_date) AS min_date, MAX(inventory_date) AS max_date FROM {inventory}"
        ),
        "regions": f"SELECT DISTINCT region_name AS value FROM {sales} ORDER BY value",
        "channels": f"SELECT DISTINCT channel_name AS value FROM {sales} ORDER BY value",
        "products": f"SELECT DISTINCT product_name AS value FROM {sales} ORDER BY value",
        "hero": (
            "SELECT "
            "SUM(CASE WHEN sales_date >= DATE '2024-03-01' AND sales_date < DATE '2024-04-01' THEN sales_amount ELSE 0 END) AS current_sales, "
            "SUM(CASE WHEN sales_date >= DATE '2024-02-01' AND sales_date < DATE '2024-03-01' THEN sales_amount ELSE 0 END) AS previous_sales, "
            "SUM(CASE WHEN sales_date >= DATE '2024-03-01' AND sales_date < DATE '2024-04-01' AND channel_name = 'Modern Trade' THEN sales_amount ELSE 0 END) AS modern_trade_sales "
            f"FROM {sales} WHERE region_name = 'Jawa Barat'"
        ),
        "worst_product": (
            "SELECT product_name, "
            "SUM(CASE WHEN sales_date >= DATE '2024-03-01' AND sales_date < DATE '2024-04-01' THEN sales_amount ELSE 0 END) - "
            "SUM(CASE WHEN sales_date >= DATE '2024-02-01' AND sales_date < DATE '2024-03-01' THEN sales_amount ELSE 0 END) AS change "
            f"FROM {sales} WHERE region_name = 'Jawa Barat' AND sales_date >= DATE '2024-02-01' "
            "GROUP BY product_name ORDER BY change ASC LIMIT 1"
        ),
        "trend": f"SELECT COUNT(DISTINCT date_format(sales_date, '%Y-%m')) AS trend_rows FROM {sales}",
    }
    results = {name: query(name, sql) for name, sql in statements.items()}
    hero = results["hero"][0]
    return DemoValidationSnapshot(
        tables={SALES_SPEC.name: results["sales_stats"][0], INVENTORY_SPEC.name: results["inventory_stats"][0]},
        regions={row["value"] for row in results["regions"]},
        channels={row["value"] for row in results["channels"]},
        products={row["value"] for row in results["products"]},
        current_sales=float(hero["current_sales"]),
        previous_sales=float(hero["previous_sales"]),
        modern_trade_sales=float(hero["modern_trade_sales"]),
        worst_product=results["worst_product"][0]["product_name"],
        trend_rows=int(results["trend"][0]["trend_rows"]),
    )


@dataclass(frozen=True)
class GoldenParityReport:
    ok: bool
    scenarios: dict[str, ParityResult]


_GOLDEN_PARITY_CASES = (
    ("decline_west_java", "Kenapa sales Jawa Barat turun bulan ini?", {}),
    ("modern_trade_follow_up", "Kalau cuma Modern Trade?", {"filters": {"region": ["Jawa Barat"]}, "date_range": {"preset": "current_month"}, "metric": "net_sales", "dimension": "region"}),
    ("declining_products", "Produk mana yang paling turun?", {"filters": {"region": ["Jawa Barat"], "channel": ["Modern Trade"]}, "date_range": {"preset": "current_month"}}),
    ("compare_regions", "Bandingkan Jawa Barat dengan Jawa Timur.", {}),
    ("three_month_trend", "Tampilkan tren sales 3 bulan terakhir.", {}),
)


def run_golden_parity(execute, project: SemanticProject, *, catalog: str, schema: str, tolerance: float = 0.001) -> GoldenParityReport:
    scenarios: dict[str, ParityResult] = {}
    for scenario_id, question, context in _GOLDEN_PARITY_CASES:
        candidate = resolve_analytical_intent(question, context, project)
        intent = AnalyticalIntent.model_validate(normalize_analytical_intent(candidate, project))
        duck_sql = generate_semantic_sql(intent, project, dialect="duckdb")
        trino_sql = generate_semantic_sql(intent, project, dialect="trino", catalog=catalog, schema=schema)
        validated_duck = validate_readonly_sql(duck_sql, project, dialect="duckdb")
        validated_trino = validate_readonly_sql(trino_sql, project, dialect="trino", catalog=catalog, schema=schema)
        if not validated_duck.valid or not validated_trino.valid:
            scenarios[scenario_id] = ParityResult(False, ("sql_validation",))
            continue
        duck_rows = execute("duckdb", validated_duck.sql)
        trino_rows = execute("trino", validated_trino.sql)
        scenarios[scenario_id] = compare_query_rows(duck_rows, trino_rows, tolerance=tolerance)
    return GoldenParityReport(all(result.ok for result in scenarios.values()), scenarios)


class TrinoValidationClient:
    """SELECT-only client for fixed bootstrap validation queries."""

    def __init__(self, config: LoaderConfig, *, connect_factory=None) -> None:
        self.config = config
        self._connect_factory = connect_factory or _loader_driver_connect
        self._connection = None

    def _connect(self):
        self.config.validate()
        if self._connection is None:
            self._connection = self._connect_factory(
                host=self.config.host,
                port=self.config.port,
                http_scheme=self.config.http_scheme,
                catalog=self.config.catalog,
                schema=self.config.schema,
                user=self.config.user,
                auth_kind=self.config.auth_kind,
                password=self.config.password,
                access_token=self.config.access_token,
                verify_ssl=self.config.verify_ssl,
                connect_timeout_seconds=self.config.connect_timeout_seconds,
                query_timeout_seconds=self.config.query_timeout_seconds,
            )
        return self._connection

    def query(self, _name: str, sql: str) -> list[dict[str, Any]]:
        parsed = sqlglot.parse(sql, read="trino")
        if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise ValidationFailure("validation query rejected")
        cursor = self._connect().cursor()
        try:
            cursor.execute(sql)
            names = [str(item[0]) for item in (cursor.description or [])]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
