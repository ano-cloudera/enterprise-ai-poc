from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Iterable

from pydantic import SecretStr
import sqlglot
from sqlglot import exp

from app.bootstrap.config import LoaderConfig
from app.bootstrap.tempo_data import (
    APPROVED_TABLES, DUCKDB_SOURCED_SPECS, EXTENDED_APPROVED_TABLES, INVENTORY_SPEC, SALES_SPEC,
    TempoExtendedBundle, TempoFixtureBundle,
)


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LoaderSafetyError(RuntimeError):
    pass


def _qualified_for(allowed_tables: frozenset[str] | set[str], catalog: str, schema: str, table: str) -> str:
    if table not in allowed_tables or not all(_IDENTIFIER.fullmatch(part) for part in (catalog, schema, table)):
        raise LoaderSafetyError("LOADER_TARGET_REJECTED")
    return f"{catalog}.{schema}.{table}"


def _qualified(catalog: str, schema: str, table: str) -> str:
    return _qualified_for(APPROVED_TABLES, catalog, schema, table)


def _validate_loader_sql_for(allowed_tables: frozenset[str] | set[str], sql: str, catalog: str, schema: str) -> None:
    try:
        statements = sqlglot.parse(sql, read="trino")
    except Exception as exc:
        raise LoaderSafetyError("LOADER_SQL_REJECTED") from exc
    if len(statements) != 1:
        raise LoaderSafetyError("LOADER_SQL_REJECTED")
    root = statements[0]
    allowed_type = isinstance(root, (exp.Create, exp.Delete, exp.Insert))
    if not allowed_type:
        raise LoaderSafetyError("LOADER_SQL_REJECTED")
    upper = sql.strip().upper()
    if isinstance(root, exp.Create) and not (upper.startswith("CREATE SCHEMA IF NOT EXISTS ") or upper.startswith("CREATE TABLE IF NOT EXISTS ")):
        raise LoaderSafetyError("LOADER_SQL_REJECTED")
    if isinstance(root, exp.Delete) and not upper.startswith("DELETE FROM "):
        raise LoaderSafetyError("LOADER_SQL_REJECTED")
    if isinstance(root, exp.Insert) and not upper.startswith("INSERT INTO "):
        raise LoaderSafetyError("LOADER_SQL_REJECTED")
    if upper.startswith("CREATE SCHEMA"):
        if not re.fullmatch(rf"CREATE SCHEMA IF NOT EXISTS {re.escape(catalog)}\.{re.escape(schema)}", sql.strip(), re.I):
            raise LoaderSafetyError("LOADER_TARGET_REJECTED")
        return
    tables = list(root.find_all(exp.Table))
    if not tables:
        raise LoaderSafetyError("LOADER_TARGET_REJECTED")
    target = tables[0]
    qualified = ".".join(part for part in (target.catalog, target.db, target.name) if part)
    if qualified.lower() not in {_qualified_for(allowed_tables, catalog, schema, table).lower() for table in allowed_tables}:
        raise LoaderSafetyError("LOADER_TARGET_REJECTED")
    if isinstance(root, exp.Insert) and not isinstance(root.expression, exp.Values):
        raise LoaderSafetyError("LOADER_SQL_REJECTED")


def validate_loader_sql(sql: str, catalog: str, schema: str) -> None:
    _validate_loader_sql_for(APPROVED_TABLES, sql, catalog, schema)


def _build_insert_statement_for(allowed_tables: frozenset[str] | set[str], catalog: str, schema: str, table: str, columns: Iterable[str], row_count: int) -> str:
    target = _qualified_for(allowed_tables, catalog, schema, table)
    names = tuple(columns)
    if row_count < 1 or not names or any(not _IDENTIFIER.fullmatch(name) for name in names):
        raise LoaderSafetyError("LOADER_INSERT_REJECTED")
    row = "(" + ", ".join("?" for _ in names) + ")"
    return f"INSERT INTO {target} ({', '.join(names)}) VALUES " + ", ".join(row for _ in range(row_count))


def build_insert_statement(catalog: str, schema: str, table: str, columns: Iterable[str], row_count: int) -> str:
    return _build_insert_statement_for(APPROVED_TABLES, catalog, schema, table, columns, row_count)


def _loader_driver_connect(**config):
    from trino import auth as trino_auth
    from trino.dbapi import connect

    password: SecretStr = config.pop("password")
    token: SecretStr = config.pop("access_token")
    auth_kind = config.pop("auth_kind")
    if auth_kind == "basic":
        config["auth"] = trino_auth.BasicAuthentication(config["user"], password.get_secret_value())
    else:
        config["auth"] = trino_auth.JWTAuthentication(token.get_secret_value())
    config["verify"] = config.pop("verify_ssl")
    config["request_timeout"] = (config.pop("connect_timeout_seconds"), config.pop("query_timeout_seconds"))
    return connect(**config)


@dataclass(frozen=True)
class BootstrapReport:
    dry_run: bool
    catalog: str
    schema: str
    tables: tuple[str, ...]
    row_counts: dict[str, int]
    operations: tuple[str, ...]
    batch_size: int
    validation_status: str


class TrinoDemoLoader:
    """Dedicated write boundary. It cannot accept user-provided statements."""

    def __init__(self, config: LoaderConfig, *, connect_factory: Callable[..., Any] | None = None) -> None:
        self.config = config
        self._connect_factory = connect_factory or _loader_driver_connect

    def _connect(self):
        self.config.validate()
        return self._connect_factory(
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

    def _execute(self, cursor, sql: str, parameters=None) -> None:
        validate_loader_sql(sql, self.config.catalog, self.config.schema)
        cursor.execute(sql, parameters) if parameters is not None else cursor.execute(sql)

    def _load_rows(self, cursor, table: str, columns: tuple[str, ...], rows: tuple[dict[str, Any], ...]) -> int:
        batches = 0
        for offset in range(0, len(rows), self.config.batch_size):
            batch = rows[offset : offset + self.config.batch_size]
            sql = build_insert_statement(self.config.catalog, self.config.schema, table, columns, len(batch))
            parameters = [row[column] for row in batch for column in columns]
            self._execute(cursor, sql, parameters)
            batches += 1
        return batches

    def bootstrap(self, bundle: TempoFixtureBundle, *, validate: bool = True) -> BootstrapReport:
        self.config.validate()
        row_counts = {
            SALES_SPEC.name: len(bundle.sales_rows),
            INVENTORY_SPEC.name: len(bundle.inventory_rows),
        }
        planned = (
            "CREATE_SCHEMA",
            "CREATE_TABLE:commercial_sales_daily",
            "CREATE_TABLE:commercial_inventory_daily",
            "DELETE:commercial_sales_daily",
            "DELETE:commercial_inventory_daily",
            "INSERT:commercial_sales_daily",
            "INSERT:commercial_inventory_daily",
            "VALIDATE" if validate else "VALIDATION_SKIPPED",
        )
        if self.config.dry_run:
            return BootstrapReport(True, self.config.catalog, self.config.schema, tuple(sorted(APPROVED_TABLES)), row_counts, planned, self.config.batch_size, "DRY_RUN")

        connection = self._connect()
        cursor = connection.cursor()
        try:
            schema_sql = f"CREATE SCHEMA IF NOT EXISTS {self.config.catalog}.{self.config.schema}"
            self._execute(cursor, schema_sql)
            for ddl in bundle.ddl(self.config.catalog, self.config.schema):
                self._execute(cursor, ddl)
            for table in (SALES_SPEC.name, INVENTORY_SPEC.name):
                self._execute(cursor, f"DELETE FROM {_qualified(self.config.catalog, self.config.schema, table)}")
            self._load_rows(cursor, SALES_SPEC.name, bundle.sales_columns, bundle.sales_rows)
            self._load_rows(cursor, INVENTORY_SPEC.name, bundle.inventory_columns, bundle.inventory_rows)
        finally:
            cursor.close()
            connection.close()
        return BootstrapReport(False, self.config.catalog, self.config.schema, tuple(sorted(APPROVED_TABLES)), row_counts, planned, self.config.batch_size, "PENDING_EXTERNAL_VALIDATION" if validate else "SKIPPED")


class ExtendedTrinoLoader:
    """Write boundary for the DuckDB-sourced governed tables (product
    master, weather, market intelligence, market digital snapshot). Kept
    separate from TrinoDemoLoader/APPROVED_TABLES so the proven
    sales/inventory write boundary and its tests are untouched. Same
    full-replace-per-table semantics as TrinoDemoLoader; each table is
    DELETE FROM'd in full then re-inserted, which is safe here because
    these tables are wholesale periodic refreshes, not append logs."""

    def __init__(self, config: LoaderConfig, *, connect_factory: Callable[..., Any] | None = None) -> None:
        self.config = config
        self._connect_factory = connect_factory or _loader_driver_connect

    def _connect(self):
        self.config.validate()
        return self._connect_factory(
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

    def _execute(self, cursor, sql: str, parameters=None) -> None:
        _validate_loader_sql_for(EXTENDED_APPROVED_TABLES, sql, self.config.catalog, self.config.schema)
        cursor.execute(sql, parameters) if parameters is not None else cursor.execute(sql)

    def _load_rows(self, cursor, table: str, columns: tuple[str, ...], rows: tuple[dict[str, Any], ...]) -> int:
        batches = 0
        for offset in range(0, len(rows), self.config.batch_size):
            batch = rows[offset : offset + self.config.batch_size]
            sql = _build_insert_statement_for(EXTENDED_APPROVED_TABLES, self.config.catalog, self.config.schema, table, columns, len(batch))
            parameters = [row[column] for row in batch for column in columns]
            self._execute(cursor, sql, parameters)
            batches += 1
        return batches

    def bootstrap(self, bundle: TempoExtendedBundle, *, validate: bool = True) -> BootstrapReport:
        self.config.validate()
        present_specs = [spec for spec in DUCKDB_SOURCED_SPECS if spec.name in bundle.rows_by_table]
        row_counts = {spec.name: len(bundle.rows_by_table[spec.name]) for spec in present_specs}
        planned = (
            "CREATE_SCHEMA",
            *(f"CREATE_TABLE:{spec.name}" for spec in present_specs),
            *(f"DELETE:{spec.name}" for spec in present_specs),
            *(f"INSERT:{spec.name}" for spec in present_specs),
            "VALIDATE" if validate else "VALIDATION_SKIPPED",
        )
        tables = tuple(sorted(spec.name for spec in present_specs))
        if self.config.dry_run:
            return BootstrapReport(True, self.config.catalog, self.config.schema, tables, row_counts, planned, self.config.batch_size, "DRY_RUN")

        connection = self._connect()
        cursor = connection.cursor()
        try:
            schema_sql = f"CREATE SCHEMA IF NOT EXISTS {self.config.catalog}.{self.config.schema}"
            self._execute(cursor, schema_sql)
            for ddl in bundle.ddl(self.config.catalog, self.config.schema):
                self._execute(cursor, ddl)
            for spec in present_specs:
                self._execute(cursor, f"DELETE FROM {_qualified_for(EXTENDED_APPROVED_TABLES, self.config.catalog, self.config.schema, spec.name)}")
            for spec in present_specs:
                columns = bundle.columns(spec)
                self._load_rows(cursor, spec.name, columns, bundle.rows_by_table[spec.name])
        finally:
            cursor.close()
            connection.close()
        return BootstrapReport(False, self.config.catalog, self.config.schema, tables, row_counts, planned, self.config.batch_size, "PENDING_EXTERNAL_VALIDATION" if validate else "SKIPPED")
