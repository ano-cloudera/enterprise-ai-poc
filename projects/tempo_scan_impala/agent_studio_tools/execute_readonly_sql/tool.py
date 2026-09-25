"""Execute a read-only, gold-schema-only SQL query against Impala.

This is a DELIBERATE EXCEPTION to this project's "no free SQL" governance
principle (see ../execute_governed_query and ../../AGENT_STUDIO_SETUP.md).
It exists only as a last-resort fallback for the Data Agent, to be used
when resolve_semantic_object reports no governed metric matches the
question. Every result is labeled "governed": false so downstream agents
and the end user can never mistake it for a governed OSSIE answer.

Safety gates (all enforced here, not by the Impala backend - see
backend/app/db/impala_backend.py, which is a pure passthrough with no
protection of its own):
1. Exactly one statement.
2. That statement must parse as SELECT (sqlglot, Hive dialect - same
   dialect used by scripts/validate_tempo_impala_contract.py).
3. A textual keyword denylist as defense-in-depth, in case a future
   sqlglot version parses something unexpected as a Select node.
4. Every referenced table must be in the "gold" schema - never silver/raw,
   which are unaudited/ungoverned upstream layers.
5. A LIMIT is enforced (existing LIMIT capped at 200; injected if absent).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import sqlglot
from sqlglot import exp
from pydantic import BaseModel, Field, SecretStr

MAX_ROW_LIMIT = 200
ALLOWED_SCHEMA = "gold"
DENYLIST_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|MERGE|GRANT|REVOKE|TRUNCATE|"
    r"REPLACE|LOAD|SET|EXPLAIN|CALL)\b",
    re.IGNORECASE,
)


class UserParameters(BaseModel):
    project_root: str = Field(
        default="/home/cdsw/enterprise-ai-poc",
        description="Absolute CAI project path containing backend and projects",
    )
    # Same reasoning as execute_governed_query/tool.py: Agent Studio's tool
    # Configure UI only exposes User Parameters, so Impala credentials are
    # passed here and copied into os.environ before Settings() is built.
    impala_host: str = Field(default="", description="Impala coordinator hostname")
    impala_port: int = Field(default=443, description="Impala port")
    impala_database: str = Field(default="gold", description="Default Impala database/schema")
    impala_auth_mechanism: str = Field(default="LDAP", description="Impala auth mechanism, e.g. LDAP or PLAIN")
    impala_user: str = Field(default="", description="Impala username")
    impala_password: SecretStr = Field(default=SecretStr(""), description="Impala password")
    impala_use_ssl: bool = Field(default=True)
    impala_use_http_transport: bool = Field(default=True)
    impala_http_path: str = Field(default="cliservice")


def _apply_impala_env(config: UserParameters) -> None:
    # setdefault, not direct assignment: an externally-set DATA_BACKEND /
    # SEMANTIC_EXECUTION_MODE must win over these defaults, not be silently
    # overwritten by them.
    os.environ.setdefault("DATA_BACKEND", "impala")
    os.environ.setdefault("SEMANTIC_EXECUTION_MODE", "ossie")
    if config.impala_host:
        os.environ["IMPALA_HOST"] = config.impala_host
    os.environ["IMPALA_PORT"] = str(config.impala_port)
    os.environ["IMPALA_DATABASE"] = config.impala_database
    os.environ["IMPALA_AUTH_MECHANISM"] = config.impala_auth_mechanism
    if config.impala_user:
        os.environ["IMPALA_USER"] = config.impala_user
    secret = config.impala_password.get_secret_value()
    if secret:
        os.environ["IMPALA_PASSWORD"] = secret
    os.environ["IMPALA_USE_SSL"] = "true" if config.impala_use_ssl else "false"
    os.environ["IMPALA_USE_HTTP_TRANSPORT"] = "true" if config.impala_use_http_transport else "false"
    os.environ["IMPALA_HTTP_PATH"] = config.impala_http_path


class ToolParameters(BaseModel):
    sql: str = Field(
        description=(
            "A single read-only SELECT statement against gold.* tables only. "
            "Used only when resolve_semantic_object found no governed metric "
            "for the question - never as a first choice."
        )
    )


def _validate_readonly_select(sql: str) -> tuple[bool, str]:
    """Returns (is_valid, reason_if_invalid)."""
    if DENYLIST_PATTERN.search(sql):
        return False, "sql_contains_denylisted_keyword"

    try:
        statements = sqlglot.parse(sql, read="hive")
    except Exception as exc:  # sqlglot raises its own ParseError subclasses
        return False, f"sql_parse_failed: {exc}"

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return False, "exactly_one_statement_required"

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        return False, "only_select_statements_allowed"

    tables = list(statement.find_all(exp.Table))
    if not tables:
        return False, "no_table_reference_found"
    for table in tables:
        if table.db.lower() != ALLOWED_SCHEMA:
            return False, f"schema_not_allowed: {table.db or '(none)'}.{table.name} (only '{ALLOWED_SCHEMA}' is permitted)"

    return True, ""


def _enforce_limit(sql: str) -> str:
    parsed = sqlglot.parse_one(sql, read="hive")
    existing_limit = parsed.args.get("limit")
    if existing_limit is not None:
        try:
            limit_value = int(existing_limit.expression.this)
        except (AttributeError, ValueError, TypeError):
            limit_value = None
        if limit_value is not None and limit_value <= MAX_ROW_LIMIT:
            return parsed.sql(dialect="hive")
    parsed.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT)))
    return parsed.sql(dialect="hive")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    is_valid, reason = _validate_readonly_select(args.sql)
    if not is_valid:
        return json.dumps(
            {"status": "rejected", "reason": reason, "governed": False},
            ensure_ascii=False,
        )

    bounded_sql = _enforce_limit(args.sql)

    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    _apply_impala_env(config)
    from app.db.base import BackendExecutionContext
    from app.db.factory import get_data_backend

    try:
        result = get_data_backend().execute(
            bounded_sql,
            BackendExecutionContext(purpose="agent_studio_ad_hoc_readonly"),
        )
        payload = {
            "status": "success",
            "governed": False,
            "warning": (
                "This result is NOT from the governed OSSIE semantic layer - "
                "no published metric matched the question. Verify manually "
                "before treating it as authoritative."
            ),
            "sql_executed": bounded_sql,
            "columns": [column.name for column in result.columns],
            "rows": result.records(),
            "row_count": result.row_count,
        }
    except Exception as exc:  # DataBackendError or backend-specific failure
        payload = {"status": "unavailable", "reason": str(exc), "governed": False}
    return json.dumps(payload, ensure_ascii=False)


OUTPUT_KEY = "tool_output"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True)
    parser.add_argument("--tool-params", required=True)
    cli_args = parser.parse_args()
    output = run_tool(
        UserParameters(**json.loads(cli_args.user_params)),
        ToolParameters(**json.loads(cli_args.tool_params)),
    )
    print(OUTPUT_KEY, output)
