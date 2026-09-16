from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import re

import sqlglot
from sqlglot import exp

from app.core.config import get_settings
from app.semantic.loader import allowed_relationships, table_policies
from app.semantic.models import SemanticProject


@dataclass
class ValidationResult:
    valid: bool
    sql: str | None
    error: str | None = None


FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|merge|grant|revoke|invalidate|refresh)\b",
    re.I,
)
def _qualified_name(table: exp.Table) -> str:
    return ".".join(part for part in (table.catalog, table.db, table.name) if part).lower()


def _direct_star(select: exp.Select) -> bool:
    return any(
        isinstance(projection, exp.Star)
        or (isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star))
        for projection in select.expressions
    )


def validate_readonly_sql(
    sql: str,
    project: SemanticProject,
    dialect: str = "duckdb",
    catalog: str = "",
    schema: str = "",
) -> ValidationResult:
    """Validate SQL against table-scoped semantic policy and return dialect SQL."""
    settings = get_settings()
    if not sql or not sql.strip():
        return ValidationResult(False, None, "Empty SQL")
    if FORBIDDEN_KEYWORDS.search(sql):
        return ValidationResult(False, None, "DDL/DML statements are not allowed")
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except Exception as exc:
        return ValidationResult(False, None, f"SQL parse error: {exc}")
    if len(parsed) != 1:
        return ValidationResult(False, None, "Only one SQL statement is allowed")

    root = parsed[0]
    if not isinstance(root, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return ValidationResult(False, None, f"Only SELECT queries are allowed, got {type(root).__name__}")
    if any(_direct_star(select) for select in root.find_all(exp.Select)):
        return ValidationResult(False, None, "SELECT * is not allowed")

    try:
        policies = table_policies(project, dialect=dialect, catalog=catalog, schema=schema)
    except ValueError as exc:
        return ValidationResult(False, None, str(exc))
    cte_columns: dict[str, set[str]] = {}
    for cte in root.find_all(exp.CTE):
        cte_columns[cte.alias_or_name.lower()] = {
            expression.alias_or_name.lower()
            for expression in getattr(cte.this, "expressions", [])
            if expression.alias_or_name
        }

    physical_tables: list[tuple[exp.Table, str, dict]] = []
    aliases: dict[str, tuple[str, dict] | tuple[str, set[str]]] = {}
    for table in root.find_all(exp.Table):
        qualified = _qualified_name(table)
        if qualified in cte_columns and not table.db and not table.catalog:
            aliases[table.alias_or_name.lower()] = ("cte", cte_columns[qualified])
            continue
        policy = policies.get(qualified)
        if policy is None:
            return ValidationResult(False, None, f"Table not allowed: {qualified}")
        physical_tables.append((table, qualified, policy))
        aliases[table.alias_or_name.lower()] = (qualified, policy)
        aliases[qualified] = (qualified, policy)
    if not physical_tables:
        return ValidationResult(False, None, "A governed table is required")

    datasets = {policy["dataset"] for _, _, policy in physical_tables}
    permitted_relationships = allowed_relationships(project)
    for left, right in combinations(sorted(datasets), 2):
        if frozenset((left, right)) not in permitted_relationships:
            return ValidationResult(False, None, f"Relationship not allowed: {left} -> {right}")

    select_aliases = {alias.alias.lower() for alias in root.find_all(exp.Alias) if alias.alias}
    physical_policies = [policy for _, _, policy in physical_tables]
    for column in root.find_all(exp.Column):
        if isinstance(column.this, exp.Star):
            return ValidationResult(False, None, "SELECT * is not allowed")
        qualifier = (column.table or "").lower()
        name = column.name.lower()
        if qualifier:
            target = aliases.get(qualifier)
            if target is None:
                return ValidationResult(False, None, f"Unknown table alias: {qualifier}")
            if target[0] == "cte":
                if name not in target[1]:
                    return ValidationResult(False, None, f"Column not allowed for {qualifier}: {column.name}")
            elif name not in target[1]["columns"]:
                return ValidationResult(False, None, f"Column not allowed for {target[0]}: {column.name}")
        elif name not in select_aliases:
            matching = [policy for policy in physical_policies if name in policy["columns"]]
            if not matching:
                return ValidationResult(False, None, f"Column not allowed: {column.name}")
            if len(datasets) > 1:
                return ValidationResult(False, None, f"Column must be table-qualified in a multi-dataset query: {column.name}")

    safe_functions = set.intersection(*(policy["allowed_functions"] for policy in physical_policies))
    for function in root.find_all(exp.Anonymous):
        if function.name.lower() not in safe_functions:
            return ValidationResult(False, None, f"Function not allowed: {function.name}")

    where_nodes = list(root.find_all(exp.Where))
    for _, table_name, policy in physical_tables:
        if not policy["require_date_filter"]:
            continue
        found = False
        for where in where_nodes:
            for column in where.find_all(exp.Column):
                qualifier = (column.table or "").lower()
                if column.name.lower() not in policy["time_columns"]:
                    continue
                predicate = column.parent
                while predicate is not None and predicate is not where:
                    if isinstance(predicate, (exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between, exp.In)):
                        break
                    predicate = predicate.parent
                if predicate is None or predicate is where:
                    continue
                if not qualifier:
                    found = True
                else:
                    target = aliases.get(qualifier)
                    found = bool(target and target[0] == table_name)
                if found:
                    break
            if found:
                break
        if not found:
            return ValidationResult(False, None, f"Date filter required for table: {table_name}")

    semantic_max = min(policy["max_limit"] for policy in physical_policies)
    backend_max = settings.trino_max_rows if dialect == "trino" else settings.sql_max_rows
    max_rows = min(settings.sql_max_rows, backend_max, semantic_max)
    default_rows = min(min(policy["default_limit"] for policy in physical_policies), max_rows)
    limit = root.args.get("limit")
    if limit is None:
        root = root.limit(default_rows)
    else:
        expression = limit.expression
        if not isinstance(expression, exp.Literal) or not expression.is_int:
            return ValidationResult(False, None, "LIMIT must be a positive integer")
        requested = int(expression.this)
        if requested <= 0:
            return ValidationResult(False, None, "LIMIT must be a positive integer")
        if requested > max_rows:
            root.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))

    return ValidationResult(True, root.sql(dialect=dialect), None)
