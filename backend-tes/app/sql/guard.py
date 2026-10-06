from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|COPY|ATTACH|DETACH|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    sql: str | None = None
    error: str | None = None


def validate_readonly_sql(sql: str, *, max_rows: int, allowed_schemas: frozenset[str] = frozenset({"silver"})) -> GuardResult:
    text = (sql or "").strip().rstrip(";")
    if not text:
        return GuardResult(False, error="Empty SQL")
    if _FORBIDDEN.search(text):
        return GuardResult(False, error="Only read-only SELECT queries are allowed")
    try:
        statements = sqlglot.parse(text, read="duckdb")
    except sqlglot.errors.ParseError as exc:
        return GuardResult(False, error=f"SQL parse error: {exc}")
    if len(statements) != 1:
        return GuardResult(False, error="Only one SQL statement is allowed")
    root = statements[0]
    if not isinstance(root, exp.Select):
        return GuardResult(False, error="Only SELECT queries are allowed")
    if root.find(exp.Star):
        return GuardResult(False, error="SELECT * is not allowed — name columns explicitly")

    for table in root.find_all(exp.Table):
        catalog = (table.catalog or "").lower()
        schema = (table.db or "").lower()
        if schema and schema not in allowed_schemas:
            return GuardResult(False, error=f"Schema not allowed: {schema} (use silver.* only)")

    limit = root.args.get("limit")
    if limit is None:
        root = root.limit(max_rows)
    else:
        expression = limit.expression
        if not isinstance(expression, exp.Literal) or not expression.is_int:
            return GuardResult(False, error="LIMIT must be a positive integer")
        if int(expression.this) > max_rows:
            root.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))

    return GuardResult(True, sql=root.sql(dialect="duckdb"))
