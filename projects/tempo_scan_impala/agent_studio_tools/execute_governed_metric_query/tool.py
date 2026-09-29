"""Resolve a TEMPO business question to a governed metric AND execute it,
in one tool call.

Combines what resolve_semantic_object + get_metric_definition +
execute_governed_query (the three separate tools) do - each of those is
its own LLM-driven ReAct tool call from the Data Agent, so a single
question that needs all three costs 3 full agent reasoning round-trips
before any data comes back. This tool runs the same three
TempoOssieService steps as one Python function call: the LLM still
decides *whether* to call this tool and reads its result, but the
resolve -> definition -> execute sequence itself is no longer three
separate LLM decisions.

The three original single-purpose tools are kept as-is (not deleted) -
this is an additional tool for the Data Agent's Backstory to prefer for
the common "answer this metric question" case, not a replacement for
callers that genuinely need just one step (e.g. a future tool that only
needs a metric's definition without executing anything).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr


class UserParameters(BaseModel):
    project_root: str = Field(
        default="/home/cdsw/enterprise-ai-poc",
        description="Absolute CAI project path containing backend and projects",
    )
    # Same Impala credential fields as execute_governed_query's tool.py -
    # Agent Studio's tool Configure UI has no separate env-var section, so
    # these are copied into os.environ before Settings() is constructed.
    impala_host: str = Field(default="", description="Impala coordinator hostname")
    impala_port: int = Field(default=443, description="Impala port")
    impala_database: str = Field(default="gold", description="Default Impala database/schema")
    impala_auth_mechanism: str = Field(default="LDAP", description="Impala auth mechanism: LDAP, PLAIN, or GSSAPI (Kerberos)")
    impala_user: str = Field(default="", description="Impala username (LDAP/PLAIN only - ignored for GSSAPI)")
    impala_password: SecretStr = Field(default=SecretStr(""), description="Impala password (LDAP/PLAIN only - ignored for GSSAPI)")
    impala_use_ssl: bool = Field(default=True)
    impala_use_http_transport: bool = Field(default=True)
    impala_http_path: str = Field(default="cliservice")
    impala_kerberos_service_name: str = Field(
        default="impala",
        description="Kerberos service principal name, required when impala_auth_mechanism=GSSAPI",
    )


class ToolParameters(BaseModel):
    question: str = Field(description="The user's complete business question, verbatim")
    dimensions: list[str] = Field(default_factory=list, description="Requested breakdown dimensions, e.g. ['calmonth']")
    filters: dict[str, list[str | int | float | bool]] = Field(default_factory=dict)
    start_calmonth: int | None = None
    end_calmonth: int | None = None
    order: str = Field(default="desc", description="'asc' or 'desc'")
    limit: int = Field(default=50, ge=1, le=200)


def _apply_impala_env(config: UserParameters) -> None:
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
    os.environ["IMPALA_KERBEROS_SERVICE_NAME"] = config.impala_kerberos_service_name


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    _apply_impala_env(config)
    from app.ossie.service import OssieQueryRequest, TempoOssieService

    service = TempoOssieService()

    # Step 1: resolve - identical path the standalone resolve_semantic_object
    # tool uses (deterministic matcher, then a narrow LLM classifier only if
    # that finds nothing - see TempoOssieService.resolve_with_llm_fallback).
    resolution = asyncio.run(service.resolve_with_llm_fallback(args.question))
    if resolution.get("status") != "resolved":
        # needs_clarification / unsupported - nothing to execute. Return the
        # resolver's own result unchanged so the Data Agent's Backstory can
        # apply its existing per-status output contract without needing a
        # second tool call to find out resolution failed.
        return json.dumps({"resolution": resolution, "definition": None, "execution": None}, ensure_ascii=False)

    metric_name = resolution["metric"]

    # Step 2: definition - same lookup get_metric_definition's tool.py does.
    try:
        definition = service.get_metric_definition(metric_name)
    except KeyError:
        return json.dumps(
            {"resolution": resolution, "definition": None, "execution": None, "error": "unknown_governed_metric"},
            ensure_ascii=False,
        )

    # Step 3: execute - same call execute_governed_query's tool.py makes,
    # with the resolved metric name plus whatever dimensions/filters/time
    # range the caller supplied.
    request = OssieQueryRequest(
        metric=metric_name,
        dimensions=args.dimensions,
        filters=args.filters,
        start_calmonth=args.start_calmonth,
        end_calmonth=args.end_calmonth,
        order=args.order,
        limit=args.limit,
    )
    try:
        execution = service.execute_query(request)
    except RuntimeError as exc:
        execution = {"status": "unavailable", "reason": str(exc)}
    except (KeyError, ValueError) as exc:
        execution = {"status": "rejected", "reason": str(exc)}

    return json.dumps({"resolution": resolution, "definition": definition, "execution": execution}, ensure_ascii=False)


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
