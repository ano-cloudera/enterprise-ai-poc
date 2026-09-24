"""Compile and execute one structured governed TEMPO metric request."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class UserParameters(BaseModel):
    project_root: str = Field(default="/home/cdsw/enterprise-ai-poc")


class ToolParameters(BaseModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, list[str | int | float | bool]] = Field(default_factory=dict)
    start_calmonth: int | None = None
    end_calmonth: int | None = None
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=200)


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
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
