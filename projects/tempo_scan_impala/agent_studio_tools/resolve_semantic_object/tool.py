"""Resolve a TEMPO business question to a governed Apache Ossie metric."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field


class UserParameters(BaseModel):
    project_root: str = Field(
        default="/home/cdsw/enterprise-ai-poc",
        description="Absolute CAI project path containing backend and projects",
    )


class ToolParameters(BaseModel):
    question: str = Field(description="The user's complete business question")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    root = Path(config.project_root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "backend"))
    from app.ossie.service import TempoOssieService

    # Tries the deterministic token/substring matcher first, then falls back
    # to an LLM classifier (constrained to the closed governed-metric list)
    # when that finds no match - same resolution path the chat backend uses
    # (see backend/app/ossie/graph_nodes.py::ossie_analytical), so this tool
    # doesn't regress to the older, more brittle deterministic-only behavior.
    result = asyncio.run(TempoOssieService().resolve_with_llm_fallback(args.question))
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
