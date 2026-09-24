"""Validate that dimensions fit the governed single-dataset metric path."""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field


class UserParameters(BaseModel):
    project_root: str = Field(default="/home/cdsw/enterprise-ai-poc")


class ToolParameters(BaseModel):
    metric: str = Field(description="Published Ossie metric name")
    dimensions: list[str] = Field(default_factory=list)


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    from app.ossie.service import TempoOssieService

    try:
        result = TempoOssieService().find_join_path(args.metric, args.dimensions)
    except KeyError:
        result = {"status": "unsupported", "reason": "unknown_governed_metric"}
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
