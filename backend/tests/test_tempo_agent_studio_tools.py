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


def test_resolve_semantic_object_uses_llm_fallback_env(monkeypatch_unused=None) -> None:
    # llm_mode defaults to "mock" in this subprocess (no QWEN_BASE_URL set),
    # so MockLLMProvider.classify_metric always reports no match - this only
    # confirms the deterministic-hit path still resolves correctly end to
    # end now that the tool calls resolve_with_llm_fallback() instead of
    # resolve(). A genuine LLM-fallback hit is covered at the unit level by
    # backend/tests/test_tempo_ossie_service.py's
    # test_llm_fallback_resolves_a_metric_the_deterministic_matcher_missed.
    result = _run(
        "resolve_semantic_object",
        {"question": "Berapa Gross Sales Q4 2024?"},
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "gross_billing_value"


def _run_readonly_sql(sql: str) -> dict:
    return _run("execute_readonly_sql", {"sql": sql})


def test_execute_readonly_sql_rejects_non_select() -> None:
    result = _run_readonly_sql("DROP TABLE gold.rpt_sat_oos_material_month")
    assert result["status"] == "rejected"
    assert result["governed"] is False
    assert "denylist" in result["reason"] or "select" in result["reason"]


def test_execute_readonly_sql_rejects_non_gold_schema() -> None:
    result = _run_readonly_sql("SELECT * FROM silver.b2b_oct_dec_2024")
    assert result["status"] == "rejected"
    assert result["governed"] is False
    assert "schema_not_allowed" in result["reason"]


def test_execute_readonly_sql_rejects_multiple_statements() -> None:
    result = _run_readonly_sql(
        "SELECT * FROM gold.corr_b2b_material_plu; DROP TABLE gold.foo;"
    )
    assert result["status"] == "rejected"
    assert result["governed"] is False


def test_execute_readonly_sql_accepts_a_valid_gold_select_and_labels_it_ungoverned() -> None:
    # Impala isn't reachable in this test environment, so the query is
    # expected to be accepted by validation and then fail at execution -
    # this still proves the validator does not reject a legitimate gold.*
    # SELECT, and that governed stays false regardless of outcome.
    result = _run_readonly_sql(
        "SELECT calmonth, dc_stock_qty FROM gold.rpt_sat_idm_dc_month LIMIT 5"
    )
    assert result["status"] in {"success", "unavailable"}
    assert result["governed"] is False

