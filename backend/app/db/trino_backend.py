from __future__ import annotations

from dataclasses import dataclass
import logging
import re
import ssl
from time import monotonic
from typing import Any, Callable
from urllib.parse import urlsplit

from pydantic import SecretStr
import sqlglot
from sqlglot import exp

from app.core.config import Settings, get_settings
from app.db.base import (
    BackendColumn,
    BackendExecutionContext,
    BackendQueryResult,
    DataBackendError,
    DataBackendHealth,
    QueryTelemetry,
    normalize_value,
)
from app.semantic.loader import load_semantic_project, table_policies


logger = logging.getLogger(__name__)
_FORBIDDEN = re.compile(r"\b(insert|update|delete|merge|drop|alter|create|truncate|call|grant|revoke)\b", re.I)


@dataclass(frozen=True)
class ParsedTrinoEndpoint:
    host: str
    port: int
    http_scheme: str


def parse_trino_jdbc_url(value: str) -> ParsedTrinoEndpoint:
    prefix = "jdbc:trino://"
    if not value.startswith(prefix):
        raise ValueError("TRINO_JDBC_URL must use jdbc:trino://")
    try:
        parsed = urlsplit("trino://" + value[len(prefix) :])
        port = parsed.port
    except ValueError as exc:
        raise ValueError("TRINO_JDBC_URL has an invalid port") from exc
    if not parsed.hostname:
        raise ValueError("TRINO_JDBC_URL must include a host")
    port = port or 443
    return ParsedTrinoEndpoint(parsed.hostname, port, "https" if port == 443 else "http")


@dataclass(frozen=True)
class TrinoConfig:
    host: str
    port: int
    http_scheme: str
    catalog: str
    schema: str
    user: str
    password: SecretStr
    access_token: SecretStr
    verify_ssl: bool
    connect_timeout_seconds: float
    query_timeout_seconds: float
    max_rows: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "TrinoConfig":
        if settings.trino_jdbc_url:
            endpoint = parse_trino_jdbc_url(settings.trino_jdbc_url)
            host, port, scheme = endpoint.host, endpoint.port, endpoint.http_scheme
        else:
            host, port, scheme = settings.trino_host.strip(), settings.trino_port, settings.trino_http_scheme
        return cls(
            host=host,
            port=port,
            http_scheme=scheme,
            catalog=settings.trino_catalog.strip(),
            schema=settings.trino_schema.strip(),
            user=settings.trino_user.strip(),
            password=settings.trino_password,
            access_token=settings.trino_access_token,
            verify_ssl=settings.trino_verify_ssl,
            connect_timeout_seconds=settings.trino_connect_timeout_seconds,
            query_timeout_seconds=settings.trino_query_timeout_seconds,
            max_rows=settings.trino_max_rows,
        )

    @property
    def auth_kind(self) -> str:
        password = bool(self.password.get_secret_value())
        token = bool(self.access_token.get_secret_value())
        if password and token:
            raise DataBackendError("DATA_CONFIGURATION_ERROR")
        if password and not self.user:
            raise DataBackendError("DATA_CONFIGURATION_ERROR")
        return "basic" if password else "token" if token else "none"

    def validate(self) -> None:
        if not self.host or not self.catalog or not self.schema:
            raise DataBackendError("DATA_CONFIGURATION_ERROR")
        self.auth_kind


def _driver_connect(**config):
    try:
        from trino import auth as trino_auth
        from trino.dbapi import connect
    except ImportError as exc:
        raise DataBackendError("DATA_CONFIGURATION_ERROR") from exc

    auth_kind = config.pop("auth_kind")
    password: SecretStr = config.pop("password")
    token: SecretStr = config.pop("access_token")
    if auth_kind == "basic":
        config["auth"] = trino_auth.BasicAuthentication(config["user"], password.get_secret_value())
    elif auth_kind == "token":
        config["auth"] = trino_auth.JWTAuthentication(token.get_secret_value())
    query_timeout = config.pop("query_timeout_seconds")
    connect_timeout = config.pop("connect_timeout_seconds")
    config["request_timeout"] = (connect_timeout, query_timeout)
    config["verify"] = config.pop("verify_ssl")
    return connect(**config)


def _safe_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    response = getattr(exc, "http_response", None)
    status = getattr(response, "status_code", None)
    if isinstance(exc, TimeoutError) or "timeout" in name or "timed out" in message:
        return "DATA_QUERY_TIMEOUT"
    if isinstance(exc, ssl.SSLError) or any(term in message for term in ("certificate", "tls", "ssl")):
        return "DATA_TLS_ERROR"
    if isinstance(exc, PermissionError) or status in (401, 403) or any(term in message for term in ("unauthorized", "forbidden", "authentication")):
        return "DATA_AUTH_FAILED"
    if any(term in message for term in ("catalog", "schema")) and any(term in message for term in ("not exist", "not found", "invalid")):
        return "DATA_CONFIGURATION_ERROR"
    return "DATA_UNAVAILABLE"


class TrinoBackend:
    dialect = "trino"

    def __init__(self, settings: Settings | None = None, *, connect_factory: Callable[..., Any] | None = None) -> None:
        self.settings = settings or get_settings()
        try:
            self.config = TrinoConfig.from_settings(self.settings)
        except ValueError:
            self.config = TrinoConfig(
                host="",
                port=self.settings.trino_port,
                http_scheme=self.settings.trino_http_scheme,
                catalog=self.settings.trino_catalog.strip(),
                schema=self.settings.trino_schema.strip(),
                user=self.settings.trino_user.strip(),
                password=self.settings.trino_password,
                access_token=self.settings.trino_access_token,
                verify_ssl=self.settings.trino_verify_ssl,
                connect_timeout_seconds=self.settings.trino_connect_timeout_seconds,
                query_timeout_seconds=self.settings.trino_query_timeout_seconds,
                max_rows=self.settings.trino_max_rows,
            )
        self._connect_factory = connect_factory or _driver_connect
        self._connection = None

    def _connection_args(self) -> dict[str, Any]:
        self.config.validate()
        return {
            "host": self.config.host,
            "port": self.config.port,
            "http_scheme": self.config.http_scheme,
            "catalog": self.config.catalog,
            "schema": self.config.schema,
            "user": self.config.user,
            "auth_kind": self.config.auth_kind,
            "password": self.config.password,
            "access_token": self.config.access_token,
            "verify_ssl": self.config.verify_ssl,
            "connect_timeout_seconds": self.config.connect_timeout_seconds,
            "query_timeout_seconds": self.config.query_timeout_seconds,
        }

    def _connect(self):
        if self._connection is None:
            self._connection = self._connect_factory(**self._connection_args())
        return self._connection

    def _govern_and_cap(self, query: str) -> str:
        if not query.strip() or _FORBIDDEN.search(query):
            raise DataBackendError("DATA_QUERY_REJECTED")
        try:
            statements = sqlglot.parse(query, read="trino")
        except Exception as exc:
            raise DataBackendError("DATA_QUERY_REJECTED") from exc
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise DataBackendError("DATA_QUERY_REJECTED")
        root = statements[0]
        ctes = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
        policies = table_policies(
            load_semantic_project(self.settings.project_id),
            dialect="trino",
            catalog=self.config.catalog,
            schema=self.config.schema,
        )
        for table in root.find_all(exp.Table):
            if table.name.lower() in ctes and not table.db and not table.catalog:
                continue
            qualified = ".".join(part for part in (table.catalog, table.db, table.name) if part).lower()
            if qualified not in policies:
                raise DataBackendError("DATA_QUERY_REJECTED")
        limit = root.args.get("limit")
        if limit is None or not limit.expression.is_int or int(limit.expression.this) > self.config.max_rows:
            root.set("limit", exp.Limit(expression=exp.Literal.number(self.config.max_rows)))
        return root.sql(dialect="trino")

    def execute(self, query: str, context: BackendExecutionContext | None = None) -> BackendQueryResult:
        context = context or BackendExecutionContext()
        started = monotonic()
        cursor = None
        try:
            governed_query = self._govern_and_cap(query)
            cursor = self._connect().cursor()
            cursor.execute(governed_query)
            rows = cursor.fetchmany(self.config.max_rows)
            columns = [BackendColumn(name=str(item[0]), type=str(item[1]).lower()) for item in (cursor.description or [])]
            normalized = [[normalize_value(value) for value in row] for row in rows]
            latency = (monotonic() - started) * 1000
            telemetry = QueryTelemetry(
                data_backend="trino",
                catalog=self.config.catalog,
                schema=self.config.schema,
                query_latency_ms=latency,
                row_count=len(normalized),
                success=True,
            )
            logger.info(
                "data_query backend=trino catalog=%s schema=%s latency_ms=%.2f rows=%d success=true trace_id=%s",
                self.config.catalog,
                self.config.schema,
                latency,
                len(normalized),
                context.trace_id,
            )
            return BackendQueryResult(columns=columns, rows=normalized, row_count=len(normalized), telemetry=telemetry)
        except DataBackendError:
            raise
        except Exception as exc:
            code = _safe_error(exc)
            latency = (monotonic() - started) * 1000
            telemetry = QueryTelemetry(
                data_backend="trino",
                catalog=self.config.catalog or None,
                schema=self.config.schema or None,
                query_latency_ms=latency,
                row_count=0,
                success=False,
                safe_error_code=code,
            )
            self.close()
            logger.warning(
                "data_query backend=trino catalog=%s schema=%s success=false error_code=%s trace_id=%s",
                self.config.catalog or None,
                self.config.schema or None,
                code,
                context.trace_id,
            )
            raise DataBackendError(code, telemetry=telemetry) from exc
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def health_check(self, probe: bool = False) -> DataBackendHealth:
        try:
            self.config.validate()
        except (DataBackendError, ValueError):
            return DataBackendHealth(type="trino", status="misconfigured", catalog=self.config.catalog or None, schema=self.config.schema or None)
        if not probe:
            return DataBackendHealth(type="trino", status="unknown", catalog=self.config.catalog, schema=self.config.schema)
        cursor = None
        try:
            cursor = self._connect().cursor()
            cursor.execute("SELECT 1")
            cursor.fetchmany(1)
            return DataBackendHealth(type="trino", status="ok", catalog=self.config.catalog, schema=self.config.schema)
        except Exception as exc:
            code = exc.code if isinstance(exc, DataBackendError) else _safe_error(exc)
            status = {
                "DATA_AUTH_FAILED": "auth_required" if self.config.auth_kind == "none" else "auth_failed",
                "DATA_CONFIGURATION_ERROR": "misconfigured",
            }.get(code, "unavailable")
            return DataBackendHealth(type="trino", status=status, catalog=self.config.catalog, schema=self.config.schema)
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None
