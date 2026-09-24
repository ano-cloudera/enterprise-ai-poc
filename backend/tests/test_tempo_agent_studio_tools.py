from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "projects" / "tempo_scan_impala" / "agent_studio_tools"


def _run(tool: str, params: dict) -> dict:
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


def test_execute_tool_is_default_off() -> None:
    result = _run(
        "execute_governed_query",
        {"metric": "gross_billing_value", "dimensions": ["calmonth"]},
    )
    assert result == {
        "status": "unavailable",
        "reason": "OSSIE_SEMANTIC_MODE_DISABLED",
    }

