from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import logging
import ssl

import pytest

from app.api.routes import health as health_route
from app.core.config import Settings
from app.db.base import BackendExecutionContext, DataBackendError, DataBackendHealth, normalize_value
from app.db.duckdb_backend import DuckDBBackend
from app.db.factory import build_data_backend
from app.db.trino_backend import TrinoBackend, TrinoConfig, parse_trino_jdbc_url


JDBC_URL = "jdbc:trino://ano03-trino-demo.dw-ano03-cdp-env.a465-9q4k.cloudera.site:443"


def settings(**overrides) -> Settings:
    values = {
        "data_backend": "trino",
        # TrinoBackend._govern_and_cap loads the semantic project for its
        # table/column allowlist - trino's governed dataset config lives
        # under the tempo_scan synthetic project, not tempo_scan_impala
        # (which has no app/semantic/ manifest of its own).
        "project_id": "tempo_scan",
        "trino_jdbc_url": JDBC_URL,
        "trino_catalog": "tempo",
        "trino_schema": "commercial",
        "trino_user": "reader",
        "trino_max_rows": 500,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class FakeCursor:
    description = [("region_name", "varchar"), ("net_sales", "decimal(18,3)")]

    def __init__(self, *, rows=None, error=None):
        self.rows = rows if rows is not None else [("Jawa Barat", Decimal("75521.278"))]
        self.error = error
        self.executed = []
        self.closed = False

    def execute(self, sql):
        self.executed.append(sql)
        if self.error:
            raise self.error

    def fetchmany(self, size):
        return self.rows[:size]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def backend(*, cursor=None, **overrides):
    cursor = cursor or FakeCursor()
    connection = FakeConnection(cursor)
    calls = []

    def connect_factory(**kwargs):
        calls.append(kwargs)
        return connection

    instance = TrinoBackend(settings(**overrides), connect_factory=connect_factory)
    return instance, cursor, connection, calls


def test_factory_selects_duckdb():
    assert isinstance(build_data_backend(settings(data_backend="duckdb")), DuckDBBackend)


def test_factory_selects_trino():
    assert isinstance(build_data_backend(settings()), TrinoBackend)


def test_duckdb_initialization_is_safe_for_concurrent_local_requests(tmp_path):
    local_settings = Settings(_env_file=None, data_backend="duckdb", project_id="tempo_scan", duckdb_path=tmp_path / "concurrent.duckdb")
    instance = DuckDBBackend(local_settings)
    sql = "SELECT region_name FROM commercial_sales_daily LIMIT 1"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(instance.execute, [sql] * 4))
    assert all(result.row_count == 1 for result in results)


def test_jdbc_parser_extracts_host():
    assert parse_trino_jdbc_url(JDBC_URL).host.startswith("ano03-trino-demo")


def test_jdbc_parser_extracts_port():
    assert parse_trino_jdbc_url(JDBC_URL).port == 443


def test_jdbc_parser_selects_https_for_443():
    assert parse_trino_jdbc_url(JDBC_URL).http_scheme == "https"


@pytest.mark.parametrize("url", ["postgres://host:443", "jdbc:trino://", "jdbc:trino://host:notaport"])
def test_jdbc_parser_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        parse_trino_jdbc_url(url)


def test_explicit_host_configuration_is_supported():
    config = TrinoConfig.from_settings(settings(trino_jdbc_url="", trino_host="trino.internal", trino_port=8443))
    assert (config.host, config.port) == ("trino.internal", 8443)


def test_missing_endpoint_is_safe_configuration_error():
    instance = TrinoBackend(settings(trino_jdbc_url="", trino_host=""))
    with pytest.raises(DataBackendError, match="DATA_CONFIGURATION_ERROR"):
        instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")


def test_username_password_auth_is_passed_without_logging_secret():
    instance, _, _, calls = backend(trino_password="top-secret")
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    assert calls[0]["auth_kind"] == "basic"
    assert "top-secret" not in repr(calls[0])


def test_token_auth_is_passed_without_logging_secret():
    instance, _, _, calls = backend(trino_access_token="bearer-secret")
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    assert calls[0]["auth_kind"] == "token"
    assert "bearer-secret" not in repr(calls[0])


def test_no_auth_mode_does_not_invent_credentials():
    instance, _, _, calls = backend(trino_user="")
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    assert calls[0]["auth_kind"] == "none"
    assert calls[0]["user"] == ""


def test_ambiguous_auth_is_rejected():
    instance, *_ = backend(trino_password="secret", trino_access_token="token")
    with pytest.raises(DataBackendError, match="DATA_CONFIGURATION_ERROR"):
        instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")


def test_config_repr_redacts_secrets():
    config = TrinoConfig.from_settings(settings(trino_password="top-secret", trino_access_token="bearer-secret"))
    rendered = repr(config)
    assert "top-secret" not in rendered
    assert "bearer-secret" not in rendered


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT region_name FROM tempo.commercial.commercial_sales_daily",
        "WITH governed AS (SELECT region_name FROM tempo.commercial.commercial_sales_daily) SELECT region_name FROM governed",
    ],
)
def test_read_queries_are_accepted(sql):
    instance, cursor, *_ = backend()
    assert instance.execute(sql).row_count == 1
    assert cursor.closed


@pytest.mark.parametrize("verb", ["INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE", "TRUNCATE", "CALL", "GRANT", "REVOKE"])
def test_mutating_or_privileged_statements_are_rejected(verb):
    instance, cursor, *_ = backend()
    with pytest.raises(DataBackendError, match="DATA_QUERY_REJECTED"):
        instance.execute(f"{verb} TABLE tempo.commercial.commercial_sales_daily")
    assert not cursor.executed


@pytest.mark.parametrize(
    "table",
    [
        "other.commercial.commercial_sales_daily",
        "tempo.other.commercial_sales_daily",
        "tempo.commercial.unknown_table",
        "commercial_sales_daily",
    ],
)
def test_exact_catalog_schema_table_governance(table):
    instance, *_ = backend()
    with pytest.raises(DataBackendError, match="DATA_QUERY_REJECTED"):
        instance.execute(f"SELECT region_name FROM {table}")


def test_query_limit_is_capped_by_adapter():
    instance, cursor, *_ = backend(trino_max_rows=25)
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily LIMIT 100")
    assert "LIMIT 25" in cursor.executed[0].upper()


def test_query_without_limit_gets_adapter_cap():
    instance, cursor, *_ = backend(trino_max_rows=25)
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    assert "LIMIT 25" in cursor.executed[0].upper()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError("driver timed out"), "DATA_QUERY_TIMEOUT"),
        (PermissionError("unauthorized bearer-secret"), "DATA_AUTH_FAILED"),
        (ssl.SSLError("certificate verify failed"), "DATA_TLS_ERROR"),
        (ConnectionError("cannot reach credential-bearing-uri"), "DATA_UNAVAILABLE"),
        (RuntimeError("Catalog tempo does not exist"), "DATA_CONFIGURATION_ERROR"),
    ],
)
def test_driver_errors_are_normalized(error, code):
    instance, *_ = backend(cursor=FakeCursor(error=error))
    with pytest.raises(DataBackendError) as caught:
        instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    assert caught.value.code == code
    assert str(caught.value) == code
    assert caught.value.telemetry.safe_error_code == code
    assert caught.value.telemetry.success is False


def test_normalized_result_contract_and_types():
    cursor = FakeCursor(rows=[("Jawa Barat", Decimal("75521.278"))])
    instance, *_ = backend(cursor=cursor)
    result = instance.execute("SELECT region_name, net_sales FROM tempo.commercial.commercial_sales_daily")
    assert result.model_dump() == {
        "columns": [{"name": "region_name", "type": "varchar"}, {"name": "net_sales", "type": "decimal(18,3)"}],
        "rows": [["Jawa Barat", 75521.278]],
        "row_count": 1,
        "telemetry": {
            "data_backend": "trino",
            "catalog": "tempo",
            "schema": "commercial",
            "query_latency_ms": pytest.approx(result.telemetry.query_latency_ms),
            "row_count": 1,
            "success": True,
            "safe_error_code": None,
        },
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.25"), 1.25),
        (date(2026, 9, 15), "2026-09-15"),
        (datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc), "2026-09-15T10:30:00+00:00"),
        (True, True),
        (7, 7),
        (2.5, 2.5),
        ("safe", "safe"),
        (None, None),
    ],
)
def test_json_value_normalization(value, expected):
    assert normalize_value(value) == expected


def test_connection_is_lazy_and_reused_until_closed():
    instance, _, connection, calls = backend()
    assert calls == []
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    instance.execute("SELECT region_name FROM tempo.commercial.commercial_sales_daily")
    assert len(calls) == 1
    instance.close()
    assert connection.closed


def test_health_without_probe_does_not_connect():
    instance, _, _, calls = backend()
    health = instance.health_check()
    assert health.status == "unknown"
    assert calls == []


def test_health_probe_reports_ok_safely():
    cursor = FakeCursor(rows=[(1,)])
    cursor.description = [("_col0", "integer")]
    instance, *_ = backend(cursor=cursor)
    assert instance.health_check(probe=True).status == "ok"


def test_health_missing_configuration_is_misconfigured():
    instance = TrinoBackend(settings(trino_jdbc_url="", trino_host=""))
    assert instance.health_check().status == "misconfigured"


def test_health_malformed_jdbc_url_is_misconfigured_not_an_exception():
    instance = TrinoBackend(settings(trino_jdbc_url="jdbc:trino://host:notaport"))
    assert instance.health_check().status == "misconfigured"


def test_errors_do_not_log_secrets(caplog):
    instance, *_ = backend(cursor=FakeCursor(error=PermissionError("top-secret bearer-secret")), trino_password="top-secret")
    with caplog.at_level(logging.INFO), pytest.raises(DataBackendError):
        instance.execute(
            "SELECT region_name FROM tempo.commercial.commercial_sales_daily",
            BackendExecutionContext(trace_id="trace-safe", purpose="test"),
        )
    assert "top-secret" not in caplog.text
    assert "bearer-secret" not in caplog.text


@pytest.mark.asyncio
async def test_remote_unavailable_does_not_fail_application_health(monkeypatch):
    class UnavailableBackend:
        def health_check(self, probe=False):
            return DataBackendHealth(type="trino", status="unavailable", catalog="tempo", schema="commercial")

    monkeypatch.setattr(health_route, "get_data_backend", lambda: UnavailableBackend())
    response = await health_route.health()
    assert response.status == "ok"
    assert response.data_backend.status == "unavailable"


@pytest.mark.asyncio
async def test_public_health_never_contains_data_secrets(monkeypatch):
    class SafeBackend:
        def health_check(self, probe=False):
            return DataBackendHealth(type="trino", status="unknown", catalog="tempo", schema="commercial")

    monkeypatch.setattr(health_route, "get_data_backend", lambda: SafeBackend())
    rendered = (await health_route.health()).model_dump_json()
    assert "top-secret" not in rendered
    assert "access_token" not in rendered
    assert "password" not in rendered
