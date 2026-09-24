"""Query governed TEMPO business context from Apache Ossie Core."""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field


class UserParameters(BaseModel):
    project_root: str = Field(default="/home/cdsw/enterprise-ai-poc")


class ToolParameters(BaseModel):
    question: str = Field(description="Business concept or question to explain")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    from app.ossie.service import TempoOssieService

    result = TempoOssieService().query_ontology(args.question)
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
