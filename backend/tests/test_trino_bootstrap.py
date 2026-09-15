from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from app.bootstrap.config import LoaderConfig, LoaderConfigurationError, LoaderSettings
from app.bootstrap.loader import LoaderSafetyError, TrinoDemoLoader, build_insert_statement, validate_loader_sql
from app.bootstrap.tempo_data import APPROVED_TABLES, hero_metrics, load_tempo_fixture_bundle
from app.bootstrap.validation import (
    DemoValidationSnapshot,
    ValidationFailure,
    collect_validation_snapshot,
    compare_query_rows,
    run_golden_parity,
    validate_snapshot,
)
from app.core.config import Settings
from app.db.base import DataBackendError
from app.db.trino_backend import TrinoBackend
from app.semantic.loader import load_semantic_project
from app.services.query import QueryContext, QueryValidationError, QueryService


JDBC_URL = "jdbc:trino://ano03-trino-demo.dw-ano03-cdp-env.a465-9q4k.cloudera.site:443"


def loader_settings(**overrides) -> LoaderSettings:
    values = {
        "trino_loader_jdbc_url": JDBC_URL,
        "trino_loader_catalog": "tempo",
        "trino_loader_schema": "commercial",
        "trino_loader_user": "bootstrap-user",
        "trino_loader_password": "loader-secret",
        "trino_loader_batch_size": 500,
    }
    values.update(overrides)
    return LoaderSettings(_env_file=None, **values)


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def fake_loader(**settings_overrides):
    connection = FakeConnection()
    calls = []

    def connect_factory(**kwargs):
        calls.append(kwargs)
        return connection

    loader = TrinoDemoLoader(LoaderConfig.from_settings(loader_settings(**settings_overrides)), connect_factory=connect_factory)
    return loader, connection, calls


def passing_snapshot():
    bundle = load_tempo_fixture_bundle()
    metrics = hero_metrics(bundle.sales_rows)
    return DemoValidationSnapshot(
        tables={
            "commercial_sales_daily": {"exists": True, "row_count": len(bundle.sales_rows), "columns": list(bundle.sales_columns), "null_required": 0, "min_date": "2024-01-01", "max_date": "2024-03-31"},
            "commercial_inventory_daily": {"exists": True, "row_count": len(bundle.inventory_rows), "columns": list(bundle.inventory_columns), "null_required": 0, "min_date": "2024-01-01", "max_date": "2024-03-31"},
        },
        regions={"Jawa Barat", "Jawa Timur"},
        channels={"Modern Trade", "General Trade"},
        products={"Bodrex Flu & Batuk", "Tempra"},
        current_sales=metrics.current_sales,
        previous_sales=metrics.previous_sales,
        modern_trade_sales=metrics.modern_trade_sales,
        worst_product=metrics.worst_product,
        trend_rows=3,
    )


def test_loader_config_never_reuses_application_credentials(monkeypatch):
    monkeypatch.setenv("TRINO_USER", "runtime-user")
    monkeypatch.setenv("TRINO_PASSWORD", "runtime-secret")
    config = LoaderConfig.from_settings(loader_settings(trino_loader_user="", trino_loader_password=""))
    with pytest.raises(LoaderConfigurationError):
        config.validate()
    assert config.user == ""


def test_missing_loader_configuration_fails_safely():
    config = LoaderConfig.from_settings(LoaderSettings(_env_file=None))
    with pytest.raises(LoaderConfigurationError, match="LOADER_CONFIGURATION_INCOMPLETE"):
        config.validate()


def test_loader_jdbc_parser_uses_known_endpoint():
    config = LoaderConfig.from_settings(loader_settings())
    assert config.host.startswith("ano03-trino-demo")
    assert config.port == 443
    assert config.http_scheme == "https"


def test_loader_secret_values_are_hidden():
    rendered = repr(LoaderConfig.from_settings(loader_settings(trino_loader_access_token="token-secret", trino_loader_password="")))
    assert "token-secret" not in rendered
    assert "loader-secret" not in rendered


def test_runtime_settings_do_not_define_loader_secrets():
    runtime = Settings(_env_file=None)
    assert not hasattr(runtime, "trino_loader_password")
    assert not hasattr(runtime, "trino_loader_access_token")


def test_only_expected_tempo_tables_are_approved():
    assert APPROVED_TABLES == {"commercial_sales_daily", "commercial_inventory_daily"}


@pytest.mark.parametrize("table", ["users", "system.runtime.nodes", "commercial_sales_daily_backup"])
def test_unknown_loader_table_is_rejected(table):
    with pytest.raises(LoaderSafetyError):
        build_insert_statement("tempo", "commercial", table, ["id"], 1)


@pytest.mark.parametrize("operation", ["CREATE SCHEMA", "CREATE TABLE", "DELETE FROM", "INSERT INTO"])
def test_loader_write_allowlist_accepts_scoped_operations(operation):
    table = "commercial_sales_daily"
    sql = {
        "CREATE SCHEMA": "CREATE SCHEMA IF NOT EXISTS tempo.commercial",
        "CREATE TABLE": f"CREATE TABLE IF NOT EXISTS tempo.commercial.{table} (sales_date DATE)",
        "DELETE FROM": f"DELETE FROM tempo.commercial.{table}",
        "INSERT INTO": f"INSERT INTO tempo.commercial.{table} (sales_date) VALUES (?)",
    }[operation]
    validate_loader_sql(sql, "tempo", "commercial")


@pytest.mark.parametrize("sql", ["DROP TABLE tempo.commercial.commercial_sales_daily", "SELECT * FROM system.runtime.nodes", "UPDATE tempo.commercial.commercial_sales_daily SET sales_amount=0", "CALL system.flush_metadata_cache()"])
def test_arbitrary_or_unapproved_loader_sql_is_rejected(sql):
    with pytest.raises(LoaderSafetyError):
        validate_loader_sql(sql, "tempo", "commercial")


def test_fixture_bundle_is_deterministic():
    first = load_tempo_fixture_bundle()
    second = load_tempo_fixture_bundle()
    assert first.fingerprint == second.fingerprint
    assert first.sales_rows == second.sales_rows


def test_hero_jawa_barat_values_are_stable():
    metrics = hero_metrics(load_tempo_fixture_bundle().sales_rows)
    assert metrics.current_sales == pytest.approx(75521.278, abs=0.001)
    assert metrics.previous_sales == pytest.approx(90575.469, abs=0.001)
    assert metrics.decline_pct == pytest.approx(-16.6206, abs=0.001)


def test_modern_trade_subset_is_stable():
    assert hero_metrics(load_tempo_fixture_bundle().sales_rows).modern_trade_sales == pytest.approx(24219.119, abs=0.001)


def test_product_decline_ranking_is_stable():
    metrics = hero_metrics(load_tempo_fixture_bundle().sales_rows)
    assert metrics.worst_product == "Bodrex Flu & Batuk"
    assert metrics.worst_product_change < 0


def test_table_ddl_parses_as_trino_and_uses_simple_types():
    bundle = load_tempo_fixture_bundle()
    statements = bundle.ddl("tempo", "commercial")
    assert len(statements) == 2
    for sql in statements:
        validate_loader_sql(sql, "tempo", "commercial")
        assert all(complex_type not in sql for complex_type in ("ARRAY", "MAP", "ROW("))


def test_insert_statement_is_qualified_and_parameterized():
    sql = build_insert_statement("tempo", "commercial", "commercial_sales_daily", ["sales_date", "sales_amount"], 2)
    assert sql.startswith("INSERT INTO tempo.commercial.commercial_sales_daily")
    assert sql.count("?") == 4


def test_batch_size_is_enforced():
    loader, connection, _ = fake_loader(trino_loader_batch_size=10000)
    report = loader.bootstrap(load_tempo_fixture_bundle(limit=501), validate=False)
    inserts = [sql for sql, _ in connection.cursor_instance.calls if sql.startswith("INSERT INTO")]
    assert len(inserts) == 4  # 501 sales + 501 inventory, capped to 500 rows per batch
    assert report.batch_size == 500


def test_dry_run_performs_no_connection_or_writes():
    loader, _, connection_calls = fake_loader(trino_loader_dry_run=True)
    report = loader.bootstrap(load_tempo_fixture_bundle(limit=10), validate=False)
    assert report.dry_run is True
    assert connection_calls == []
    assert report.row_counts == {"commercial_sales_daily": 10, "commercial_inventory_daily": 10}


def test_dry_run_does_not_require_loader_credentials():
    config = LoaderConfig.from_settings(loader_settings(trino_loader_user="", trino_loader_password="", trino_loader_dry_run=True))
    loader = TrinoDemoLoader(config, connect_factory=lambda **_: pytest.fail("dry run connected"))
    assert loader.bootstrap(load_tempo_fixture_bundle(limit=1), validate=False).dry_run


def test_rerunning_bootstrap_uses_scoped_delete_before_insert():
    loader, connection, _ = fake_loader()
    bundle = load_tempo_fixture_bundle(limit=2)
    loader.bootstrap(bundle, validate=False)
    loader.bootstrap(bundle, validate=False)
    sql = [item[0] for item in connection.cursor_instance.calls]
    assert sql.count("DELETE FROM tempo.commercial.commercial_sales_daily") == 2
    assert sql.count("DELETE FROM tempo.commercial.commercial_inventory_daily") == 2


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda snap: snap.tables["commercial_sales_daily"].update(exists=False), "missing"),
        (lambda snap: snap.tables["commercial_sales_daily"].update(row_count=1), "row count"),
        (lambda snap: setattr(snap, "current_sales", 1.0), "hero"),
    ],
)
def test_post_load_validation_detects_failures(mutation, message):
    snapshot = passing_snapshot()
    mutation(snapshot)
    with pytest.raises(ValidationFailure, match=message):
        validate_snapshot(snapshot, load_tempo_fixture_bundle())


def test_post_load_validation_accepts_canonical_snapshot():
    report = validate_snapshot(passing_snapshot(), load_tempo_fixture_bundle())
    assert report.ok and report.hero_scenario == "PASS"


def test_live_snapshot_collector_uses_fixed_validation_queries():
    canonical = passing_snapshot()
    responses = {
        "sales_stats": [canonical.tables["commercial_sales_daily"]],
        "inventory_stats": [canonical.tables["commercial_inventory_daily"]],
        "regions": [{"value": value} for value in canonical.regions],
        "channels": [{"value": value} for value in canonical.channels],
        "products": [{"value": value} for value in canonical.products],
        "hero": [{"current_sales": canonical.current_sales, "previous_sales": canonical.previous_sales, "modern_trade_sales": canonical.modern_trade_sales}],
        "worst_product": [{"product_name": canonical.worst_product}],
        "trend": [{"trend_rows": canonical.trend_rows}],
    }
    seen = []

    def query(name, sql):
        seen.append((name, sql))
        return responses[name]

    collected = collect_validation_snapshot(query, "tempo", "commercial")
    assert collected.current_sales == pytest.approx(canonical.current_sales)
    assert {name for name, _ in seen} == set(responses)
    assert all("tempo.commercial." in sql for name, sql in seen if name not in {"regions", "channels", "products"} or "information_schema" not in sql)


def test_five_golden_parity_runner_reports_each_scenario():
    calls = []

    def execute(dialect, sql):
        calls.append((dialect, sql))
        return [{"value": 1.0000001}]

    report = run_golden_parity(execute, load_semantic_project(), catalog="tempo", schema="commercial")
    assert report.ok
    assert set(report.scenarios) == {"decline_west_java", "modern_trade_follow_up", "declining_products", "compare_regions", "three_month_trend"}
    assert len(calls) == 10


def test_parity_comparison_uses_float_tolerance_and_row_shape():
    duck = [{"region": "Jawa Barat", "value": 75521.278}]
    trino = [{"region": "Jawa Barat", "value": Decimal("75521.2780001")}]
    assert compare_query_rows(duck, trino, tolerance=0.001).ok
    assert not compare_query_rows(duck, [{"region": "Jawa Timur", "value": 1}], tolerance=0.001).ok


def test_application_trino_backend_remains_read_only():
    backend = TrinoBackend(Settings(_env_file=None, data_backend="trino"))
    with pytest.raises(DataBackendError, match="DATA_QUERY_REJECTED"):
        backend.execute("CREATE TABLE tempo.commercial.nope (id BIGINT)")


def test_query_service_remains_incapable_of_writes():
    service = QueryService()
    with pytest.raises(QueryValidationError):
        service.execute_validated("DELETE FROM commercial_sales_daily", QueryContext(purpose="test"))


def test_semantic_trino_tables_align_with_loader_allowlist():
    project = load_semantic_project()
    governed = {dataset.trino.table for dataset in project.datasets.values()}
    assert APPROVED_TABLES.issubset(governed)
    assert "commercial_sales_forecast" in governed
    assert "commercial_sales_forecast" not in APPROVED_TABLES
