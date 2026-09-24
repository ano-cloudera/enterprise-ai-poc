from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "projects" / "tempo_scan_impala" / "agent_studio_tools"


def _run(tool: str, params: dict, *, env: dict | None = None) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS / tool / "tool.py"),
            "--user-params",
            json.dumps({"project_root": str(ROOT)}),
            "--tool-params",
            json.dumps(params),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    prefix = "tool_output "
    assert result.stdout.startswith(prefix)
    return json.loads(result.stdout[len(prefix) :])


def test_resolve_semantic_object_tool() -> None:
    result = _run(
        "resolve_semantic_object",
        {"question": "Berapa Gross Sales Q4 2024?"},
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "gross_billing_value"


def test_get_metric_definition_tool() -> None:
    result = _run("get_metric_definition", {"metric": "company_fill_rate"})
    assert result["status"] == "success"
    assert result["definition"]["metric_id"] == "FL-01-EXEC"


def test_find_join_path_refuses_unsupported_dimension() -> None:
    result = _run(
        "find_join_path",
        {"metric": "gross_billing_value", "dimensions": ["customer"]},
    )
    assert result["status"] == "unsupported"
    assert result["instruction"].startswith("Extend the semantic contract")


def test_execute_tool_is_blocked_when_semantic_mode_is_legacy() -> None:
    # OSSIE/Impala is enabled by default now; this covers the explicit
    # opt-out path (SEMANTIC_EXECUTION_MODE=legacy) rather than a default.
    result = _run(
        "execute_governed_query",
        {"metric": "gross_billing_value", "dimensions": ["calmonth"]},
        env={"SEMANTIC_EXECUTION_MODE": "legacy"},
    )
    assert result == {
        "status": "unavailable",
        "reason": "OSSIE_SEMANTIC_MODE_DISABLED",
    }

