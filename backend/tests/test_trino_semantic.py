from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.semantic.intent import AnalyticalIntent
from app.semantic.loader import load_semantic_project, table_policies
from app.semantic.resolver import normalize_analytical_intent, resolve_analytical_intent
from app.tools.semantic_sql import generate_semantic_sql
from app.tools.sql_validator import validate_readonly_sql


PROJECT = load_semantic_project()
CATALOG = "tempo"
SCHEMA = "commercial"


def normalized(question: str, context=None) -> AnalyticalIntent:
    return normalize_analytical_intent(resolve_analytical_intent(question, context or {}, PROJECT), PROJECT)


def signature(sql: str, dialect: str) -> dict:
    root = sqlglot.parse_one(sql, read=dialect)
    return {
        "projections": sorted(item.alias_or_name for item in root.expressions),
        "columns": sorted({column.name for column in root.find_all(exp.Column)}),
        "literals": sorted({str(item.this) for item in root.find_all(exp.Literal)}),
        "groups": len(list(root.find_all(exp.Group))),
        "orders": len(list(root.find_all(exp.Order))),
        "limit": root.args["limit"].expression.this,
    }


def test_project_trino_table_policy_is_exactly_qualified():
    policies = table_policies(PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA)
    assert "tempo.commercial.commercial_sales_daily" in policies


def test_trino_sql_uses_governed_qualified_table():
    sql = generate_semantic_sql(normalized("Show sales trend for the last three months"), PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA)
    assert "tempo.commercial.commercial_sales_daily" in sql
    assert validate_readonly_sql(sql, PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA).valid


GOLDEN_CASES = [
    ("Why did sales decline in Jawa Barat this month?", {}),
    ("How about Modern Trade?", {"filters": {"region": ["Jawa Barat"]}, "date_range": {"preset": "current_month"}}),
    ("Which products are declining this month?", {}),
    ("Compare sales by region this month", {}),
    ("Show sales trend for the last three months", {}),
]


def test_golden_duckdb_trino_semantic_parity():
    for question, context in GOLDEN_CASES:
        intent = normalized(question, context)
        duckdb_sql = generate_semantic_sql(intent, PROJECT, dialect="duckdb")
        trino_sql = generate_semantic_sql(intent, PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA)
        assert signature(duckdb_sql, "duckdb") == signature(trino_sql, "trino")


def test_trino_rendering_preserves_filters_and_dates():
    intent = normalized("Why did sales decline in Jawa Barat this month?")
    sql = generate_semantic_sql(intent, PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA)
    assert "Jawa Barat" in sql
    assert intent.time.start in sql and intent.time.end in sql


def test_trino_rendering_preserves_grouping_and_ordering():
    sql = generate_semantic_sql(normalized("Compare sales by region this month"), PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA)
    root = sqlglot.parse_one(sql, read="trino")
    assert root.args.get("group") is not None
    assert root.args.get("order") is not None


def test_trino_rendering_preserves_comparison_logic():
    sql = generate_semantic_sql(normalized("Why did sales decline in Jawa Barat this month?"), PROJECT, dialect="trino", catalog=CATALOG, schema=SCHEMA)
    aliases = {item.alias_or_name for item in sqlglot.parse_one(sql, read="trino").expressions}
    assert {"current_value", "previous_value", "absolute_change", "percentage_change"}.issubset(aliases)
