"""Compile and execute one structured governed TEMPO metric request."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class UserParameters(BaseModel):
    project_root: str = Field(default="/home/cdsw/enterprise-ai-poc")
    # Agent Studio's tool Configure UI only exposes User Parameters (no
    # separate env-var section per tool), so Impala credentials are passed
    # here and copied into os.environ before Settings() is constructed -
    # backend/app/core/config.py's Settings is a pydantic-settings
    # BaseSettings that reads these from the process environment, the same
    # mechanism the tempo-backend CAI Application uses. impala_password is
    # SecretStr so it never renders in plain text in tool logs/output.
    impala_host: str = Field(default="", description="Impala coordinator hostname")
    impala_port: int = Field(default=443, description="Impala port")
    impala_database: str = Field(default="gold", description="Default Impala database/schema")
    impala_auth_mechanism: str = Field(default="LDAP", description="Impala auth mechanism, e.g. LDAP or PLAIN")
    impala_user: str = Field(default="", description="Impala username")
    impala_password: SecretStr = Field(default=SecretStr(""), description="Impala password")
    impala_use_ssl: bool = Field(default=True)
    impala_use_http_transport: bool = Field(default=True)
    impala_http_path: str = Field(default="cliservice")


class ToolParameters(BaseModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, list[str | int | float | bool]] = Field(default_factory=dict)
    start_calmonth: int | None = None
    end_calmonth: int | None = None
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=200)


def _apply_impala_env(config: UserParameters) -> None:
    # setdefault, not direct assignment: an externally-set DATA_BACKEND /
    # SEMANTIC_EXECUTION_MODE (e.g. an explicit opt-out for testing) must
    # win over these defaults, not be silently overwritten by them.
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


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    _apply_impala_env(config)
    from app.ossie.service import OssieQueryRequest, TempoOssieService

    service = TempoOssieService()
    request = OssieQueryRequest(**args.model_dump())
    try:
        result = service.execute_query(request)
    except RuntimeError as exc:
        result = {"status": "unavailable", "reason": str(exc)}
    except (KeyError, ValueError) as exc:
        result = {"status": "rejected", "reason": str(exc)}
    return json.dumps(result, ensure_ascii=False)


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
