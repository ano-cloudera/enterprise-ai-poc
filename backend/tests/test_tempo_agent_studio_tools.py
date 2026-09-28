from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "projects" / "tempo_scan_impala" / "agent_studio_tools"
THREE_AGENT_SETUP = (
    ROOT
    / "projects"
    / "tempo_scan_impala"
    / "agents"
    / "AGENT_STUDIO_3AGENT_SETUP.md"
)


def _run(tool: str, params: dict, *, env: dict | None = None, user_params: dict | None = None) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS / tool / "tool.py"),
            "--user-params",
            json.dumps({"project_root": str(ROOT), **(user_params or {})}),
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


@pytest.mark.parametrize(
    ("question", "metric", "metric_id"),
    [
        ("Total BILL_QTY per material Q4 2024?", "material_sell_in_quantity", "SI-02-MAT"),
        ("Total DO amount per material Q4 2024?", "material_delivery_order_amount", "SI-04-MAT"),
        ("Branch B2B mana dengan bill quantity tertinggi?", "b2b_branch_sell_out_quantity", "B2B-02-BR"),
        ("Berapa nilai stok DC SAT-IDM per bulan?", "sat_idm_dc_stock_value", "SI-03-IDM"),
        ("Berapa nilai stok store SAT-IDM per bulan?", "sat_idm_store_stock_value", "SI-04-IDM"),
        ("Material mana dengan unfulfilled quantity terbesar?", "service_unfulfilled_quantity", "FL-02"),
        ("Sales office mana dengan picking workload tertinggi?", "picking_workload_rows", "PK-04-Q4"),
        ("Sales office mana dengan unloading events terbanyak?", "unloading_event_count", "UL-02-Q4"),
    ],
)
def test_showcase_questions_resolve_through_agent_studio_tool(
    question: str, metric: str, metric_id: str
) -> None:
    result = _run("resolve_semantic_object", {"question": question})
    assert result["status"] == "resolved"
    assert result["metric"] == metric
    assert result["definition"]["metric_id"] == metric_id


@pytest.mark.parametrize(
    ("question", "metric", "metric_id", "dimension"),
    [
        (
            "Jumlah observasi promo per mekanisme Desember 2024",
            "promo_observation_count",
            "PR-03",
            "mekanisme",
        ),
        (
            "Berapa jumlah material SKU yang tercakup SAT Promo?",
            "promo_material_count",
            "PR-02",
            "reporting_month",
        ),
        (
            "Material mana paling sering muncul dalam observasi promo?",
            "promo_observation_count",
            "PR-03",
            "material_code",
        ),
        (
            "Bagaimana distribusi kode program status Y X T?",
            "promo_observation_count",
            "PR-03",
            "program_status",
        ),
    ],
)
def test_safe_sat_promo_questions_resolve_through_agent_studio_tool(
    question: str, metric: str, metric_id: str, dimension: str
) -> None:
    result = _run("resolve_semantic_object", {"question": question})
    assert result["status"] == "resolved"
    assert result["metric"] == metric
    assert result["definition"]["metric_id"] == metric_id
    assert dimension in result["definition"]["allowed_dimensions"]
    instructions = result["definition"]["ai_context"]["instructions"].lower()
    assert "december" in instructions or "desember" in instructions


@pytest.mark.parametrize(
    "question",
    [
        "Berapa promo tidak aktif Desember 2024?",
        "Berapa revenue atau ROI dari promo?",
        "Bagaimana tren promo Oktober sampai Desember 2024?",
    ],
)
def test_unsafe_or_out_of_period_sat_promo_questions_fail_closed(
    question: str,
) -> None:
    result = _run("resolve_semantic_object", {"question": question})
    assert result["status"] == "unsupported"
    assert result["reason"] == "promo_business_definition_unavailable"


def test_plain_promo_aktif_question_now_resolves() -> None:
    # Tempo confirmed 28 Sep 2026 (Pak Hieronimus Gunawan, WhatsApp) that
    # every row in the SAT Promo December data is an active promo
    # observation - program_status does not distinguish active/inactive.
    # A plain "promo aktif" question (no implied active/inactive split,
    # no ROI/attribution, no out-of-period request) is therefore now
    # answerable via promo_observation_count, unlike before this
    # confirmation when it was blocked outright.
    result = _run(
        "resolve_semantic_object",
        {"question": "Berapa promo aktif Desember 2024?"},
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "promo_observation_count"


def test_three_agent_setup_exposes_nine_domains_and_safe_promo_controls() -> None:
    setup = THREE_AGENT_SETUP.read_text(encoding="utf-8")

    assert "these nine TEMPO data domains" in setup
    assert "9. SAT Promo" in setup
    assert "Jumlah observasi promo per mekanisme Desember 2024" in setup
    assert "Bagaimana distribusi kode program status Y/X/T?" in setup
    assert "Berapa revenue atau ROI dari promo?" in setup
    assert "SAT Promo is outside" not in setup
    assert "outside the eight-domain workflow" not in setup


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


def test_execute_governed_query_forwards_impala_credentials_from_user_params() -> None:
    # Agent Studio's tool Configure UI only exposes User Parameters (no
    # separate env-var section), so Impala credentials must be passed as
    # UserParameters fields and copied into the process environment before
    # Settings() is built - see execute_governed_query/tool.py's
    # _apply_impala_env(). An unreachable custom host still reaches the
    # Impala client (fails at connection, not at "no host configured") -
    # the failure reason is deliberately a safe, generic error code (see
    # DataBackendError/safe_error_code in backend/app/db/base.py), never the
    # raw hostname/credentials, so this only asserts the safe failure path
    # was reached at all rather than the default "no backend configured"
    # error that would occur if the User Parameters were never applied.
    result = _run(
        "execute_governed_query",
        {"metric": "gross_billing_value", "dimensions": ["calmonth"]},
        user_params={"impala_host": "impala-host-from-user-params.invalid", "impala_port": 21050},
    )
    assert result == {"status": "unavailable", "reason": "IMPALA_QUERY_FAILED"}


def test_execute_governed_metric_query_resolves_defines_and_executes_in_one_call() -> None:
    # This is the combined tool proposed to shorten the Data Agent's Agent
    # Studio chain: resolve_semantic_object + get_metric_definition +
    # execute_governed_query as one LLM-visible tool call instead of three.
    # Impala isn't reachable in this test environment (no real
    # IMPALA_HOST), so execution is expected to fail safely - this still
    # proves resolution and definition both ran and were included in the
    # combined result before execution was attempted.
    result = _run(
        "execute_governed_metric_query",
        {"question": "Berapa Gross Sales Q4 2024?", "dimensions": ["calmonth"]},
    )
    assert result["resolution"]["status"] == "resolved"
    assert result["resolution"]["metric"] == "gross_billing_value"
    assert result["definition"]["metric_id"] is not None
    assert result["execution"]["status"] in {"unavailable", "success"}


def test_execute_governed_metric_query_skips_definition_and_execution_when_unresolved() -> None:
    result = _run(
        "execute_governed_metric_query",
        {"question": "Berapa harga saham Tesla hari ini?"},
    )
    assert result["resolution"]["status"] in {"unsupported", "needs_clarification"}
    assert result["definition"] is None
    assert result["execution"] is None


def test_execute_governed_metric_query_forwards_impala_credentials_from_user_params() -> None:
    # Same contract as execute_governed_query's own equivalent test - the
    # combined tool must apply UserParameters-supplied Impala credentials
    # the same way, not silently ignore them because it goes through one
    # extra layer (resolve + definition) before execute_query() is called.
    result = _run(
        "execute_governed_metric_query",
        {"question": "Berapa Gross Sales Q4 2024?", "dimensions": ["calmonth"]},
        user_params={"impala_host": "impala-host-from-user-params.invalid", "impala_port": 21050},
    )
    assert result["execution"] == {"status": "unavailable", "reason": "IMPALA_QUERY_FAILED"}


def test_execute_governed_metric_query_blocked_when_semantic_mode_is_legacy() -> None:
    result = _run(
        "execute_governed_metric_query",
        {"question": "Berapa Gross Sales Q4 2024?"},
        env={"SEMANTIC_EXECUTION_MODE": "legacy"},
    )
    assert result["execution"] == {"status": "unavailable", "reason": "OSSIE_SEMANTIC_MODE_DISABLED"}


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
