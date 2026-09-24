"""Return a governed TEMPO metric definition and provenance."""

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


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    from app.ossie.service import TempoOssieService

    try:
        result = {
            "status": "success",
            "definition": TempoOssieService().get_metric_definition(args.metric),
        }
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
