from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.db.base import BackendExecutionContext, QueryTelemetry
from app.db.factory import get_data_backend
from app.semantic.loader import load_semantic_project
from app.tools.sql_validator import ValidationResult, validate_readonly_sql


class QueryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class QueryContext:
    purpose: str
    project_id: str | None = None
    trace_id: str = ""


@dataclass(frozen=True)
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    telemetry: QueryTelemetry | None = None


class QueryService:
    """The only application boundary permitted to execute analytical SQL."""

    def validate(self, sql: str, context: QueryContext) -> ValidationResult:
        project = load_semantic_project(context.project_id)
        settings = get_settings()
        dialect = "trino" if settings.data_backend == "trino" else "duckdb"
        return validate_readonly_sql(
            sql,
            project,
            dialect=dialect,
            catalog=settings.trino_catalog if dialect == "trino" else "",
            schema=settings.trino_schema if dialect == "trino" else "",
        )

    def execute_validated(self, sql: str, context: QueryContext) -> QueryResult:
        validation = self.validate(sql, context)
        if not validation.valid or not validation.sql:
            raise QueryValidationError(validation.error or "Query rejected by policy")
        result = get_data_backend().execute(
            validation.sql,
            BackendExecutionContext(trace_id=context.trace_id, purpose=context.purpose),
        )
        return QueryResult(
            sql=validation.sql,
            columns=[column.name for column in result.columns],
            rows=result.records(),
            telemetry=result.telemetry,
        )


query_service = QueryService()
