from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "projects" / "tempo_scan_impala"
MODEL_PATH = PROJECT / "ossie" / "tempo_core.ossie.yaml"
GOLDEN_PATH = PROJECT / "ossie" / "golden_questions.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_tempo_impala_contract_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_tempo_impala_contract.py"),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["datasets"] == 17
    assert payload["metrics"] == 54
    assert payload["golden_questions"] >= 50


def test_tempo_impala_model_uses_only_audited_semantic_views() -> None:
    model = _load(MODEL_PATH)
    sources = {dataset["source"] for dataset in model["datasets"]}
    # Original Semantic Contract v1 baseline (5 views) plus the 24 Sep 2026
    # journey expansion (9 more views, all built and validated against
    # Impala - see TEMPO_DATAMART_PLAN.md §8.1), the SAT Promo view, and the
    # 28 Sep 2026 Sales/Sell-In customer + sales_office breakdown (see
    # datasets/gold/24_rpt_sap_customer_office_material_month_semantic.sql).
    # Every source here must stay in sync with EXPECTED_SOURCES in
    # scripts/validate_tempo_impala_contract.py.
    assert sources == {
        "gold.rpt_sap_monthly_executive_semantic",
        "gold.rpt_sap_material_month_semantic",
        "gold.rpt_service_level_material_month_semantic",
        "gold.rpt_sap_customer_reconciliation_semantic",
        "gold.rpt_sales_office_performance_semantic",
        "gold.corr_b2b_branch_estore_month",
        "gold.corr_b2b_material_plu",
        "gold.corr_stock_tempo_month_seta",
        "gold.rpt_sat_idm_dc_month",
        "gold.rpt_sat_oos_material_month",
        "gold.corr_stock_tempo_sales_material_month",
        "gold.corr_sales_b2b_material_month",
        "gold.corr_b2b_satidm_branch_month",
        "gold.corr_satidm_oos_material_month",
        "gold.rpt_sat_promo_material_december_semantic",
        "gold.rpt_sap_customer_material_month_semantic",
        "gold.rpt_sap_sales_office_material_month_semantic",
    }
    assert model["relationships"] == []


def test_official_revenue_is_gold_bill_value_without_extra_scaling() -> None:
    model = _load(MODEL_PATH)
    metric = next(
        item for item in model["metrics"] if item["name"] == "gross_billing_value"
    )
    expression = metric["expression"]["dialects"][0]["expression"]
    assert expression == "SUM(monthly_executive.sales_bill_val)"
    assert "* 100" not in expression


def test_golden_questions_do_not_reference_unknown_published_metrics() -> None:
    model = _load(MODEL_PATH)
    golden = _load(GOLDEN_PATH)
    metrics = {metric["name"] for metric in model["metrics"]}
    datasets = {dataset["name"] for dataset in model["datasets"]}
    for question in golden["questions"]:
        if question["expected_status"] not in {"supported", "supported_with_caveat"}:
            continue
        assert question["metric"] in metrics
        assert question["dataset"] in datasets


def test_existing_foundation_defaults_remain_unchanged() -> None:
    settings = Settings()
    assert settings.project_id == "tempo_scan"
    assert settings.data_backend == "duckdb"


def test_showcase_metric_extensions_use_existing_audited_datasets() -> None:
    model = _load(MODEL_PATH)
    metrics = {item["name"]: item for item in model["metrics"]}
    expected = {
        "material_delivery_order_quantity": (
            "SUM(material_360.sales_do_qty)",
            "SI-03-MAT",
            "material_360",
        ),
        "material_delivery_order_amount": (
            "SUM(material_360.sales_do_amt)",
            "SI-04-MAT",
            "material_360",
        ),
        "b2b_branch_sell_out_quantity": (
            "SUM(b2b_branch_estore.b2b_bill_qty)",
            "B2B-02-BR",
            "b2b_branch_estore",
        ),
        "b2b_material_plu_quantity": (
            "SUM(b2b_material_plu.b2b_bill_qty)",
            "B2B-03-PLU",
            "b2b_material_plu",
        ),
        "sat_idm_dc_stock_value": (
            "SUM(sat_idm_dc_month.dc_stock_val)",
            "SI-03-IDM",
            "sat_idm_dc_month",
        ),
        "sat_idm_store_stock_value": (
            "SUM(sat_idm_dc_month.store_stock_val)",
            "SI-04-IDM",
            "sat_idm_dc_month",
        ),
        "service_unfulfilled_quantity": (
            "SUM(service_level_material.service_po_qty) - SUM(service_level_material.service_do_qty)",
            "FL-02",
            "service_level_material",
        ),
        "picking_workload_rows": (
            "SUM(sales_office_q4.picking_rows)",
            "PK-04-Q4",
            "sales_office_q4",
        ),
        "unloading_event_count": (
            "SUM(sales_office_q4.unloading_rows)",
            "UL-02-Q4",
            "sales_office_q4",
        ),
    }

    for name, (expression, metric_id, dataset) in expected.items():
        metric = metrics[name]
        assert metric["expression"]["dialects"][0]["expression"] == expression
        extension = next(
            item for item in metric["custom_extensions"]
            if item["vendor_name"] == "TEMPO"
        )
        config = json.loads(extension["data"])
        assert config["metric_id"] == metric_id
        assert config["base_dataset"] == dataset


def test_sat_idm_publishes_separate_levels_without_combined_pipeline_metric() -> None:
    model = _load(MODEL_PATH)
    metrics = {item["name"]: item for item in model["metrics"]}
    assert {
        "sat_idm_dc_stock_quantity",
        "sat_idm_dc_stock_value",
        "sat_idm_store_stock_quantity",
        "sat_idm_store_stock_value",
    } <= metrics.keys()
    assert "sat_idm_total_pipeline_stock" not in metrics
    assert "sat_idm_store_to_dc_ratio" not in metrics

    for metric_name in (
        "sat_idm_dc_stock_quantity",
        "sat_idm_dc_stock_value",
        "sat_idm_store_stock_quantity",
        "sat_idm_store_stock_value",
    ):
        metric = metrics[metric_name]
        assert "Never add" in metric["ai_context"]["instructions"]
        extension = next(
            item for item in metric["custom_extensions"]
            if item["vendor_name"] == "TEMPO"
        )
        config = json.loads(extension["data"])
        assert config["business_approval_status"] == (
            "confirmed_by_tempo_2026_09_28"
        )


def test_unverified_inventory_views_are_not_admitted_by_name_only() -> None:
    model = _load(MODEL_PATH)
    sources = {item["source"] for item in model["datasets"]}
    assert {
        "gold.corr_sales_material_total",
        "gold.rpt_picking_status_summary",
        "gold.corr_sat_promo_materials",
    }.isdisjoint(sources)

    audit = (
        ROOT / "datasets" / "audit" / "22_showcase_gold_view_contract.sql"
    ).read_text(encoding="utf-8")
    for source in (
        "gold.corr_sales_material_total",
        "gold.rpt_picking_status_summary",
        "gold.corr_sat_promo_materials",
    ):
        assert f"DESCRIBE {source};" in audit


def test_sat_promo_contract_evidence_is_recorded_before_admission() -> None:
    audit = (
        ROOT / "datasets" / "audit" / "23_sat_promo_gold_contract.sql"
    ).read_text(encoding="utf-8")
    evidence = (
        ROOT / "datasets" / "qa" / "23_sat_promo_gold_contract.md"
    ).read_text(encoding="utf-8")

    assert "DESCRIBE gold.corr_sat_promo_materials;" in audit
    assert "DESCRIBE silver.sat_promo_des_24;" in audit
    assert "TGL_DCP" in evidence
    assert "material_code" in evidence
    assert "Mekanisme" in evidence
    assert "program_status is raw and unmapped" in evidence


def test_sat_promo_semantic_view_has_safe_december_contract() -> None:
    ddl = (
        ROOT
        / "datasets"
        / "gold"
        / "23_rpt_sat_promo_material_december_semantic.sql"
    ).read_text(encoding="utf-8")
    audit = (
        ROOT / "datasets" / "audit" / "23_sat_promo_gold_contract.sql"
    ).read_text(encoding="utf-8")

    assert (
        "DROP VIEW IF EXISTS gold.rpt_sat_promo_material_december_semantic;"
        in ddl
    )
    assert (
        "CREATE VIEW gold.rpt_sat_promo_material_december_semantic AS" in ddl
    )
    assert "CREATE OR REPLACE VIEW" not in ddl
    assert "202412 AS reporting_month" in ddl
    assert "COUNT(*) AS promo_observation_count" in ddl
    assert "GROUP BY" in ddl
    assert "program_status" in ddl.lower()
    assert "DESCRIBE gold.rpt_sat_promo_material_december_semantic;" in audit
    assert "duplicate_grain_rows" in audit
    assert "negative_observation_rows" in audit


def test_sat_promo_ossie_contract_publishes_only_safe_metrics() -> None:
    model = _load(MODEL_PATH)
    datasets = {item["name"]: item for item in model["datasets"]}
    metrics = {item["name"]: item for item in model["metrics"]}

    dataset = datasets["sat_promo_material_december"]
    assert dataset["source"] == "gold.rpt_sat_promo_material_december_semantic"
    assert dataset["primary_key"] == [
        "reporting_month",
        "material_code",
        "mekanisme",
        "program_status",
    ]
    assert {field["name"] for field in dataset["fields"]} == {
        "reporting_month",
        "material_code",
        "mekanisme",
        "program_status",
        "promo_observation_count",
    }

    expected = {
        "promo_observation_count": (
            "SUM(sat_promo_material_december.promo_observation_count)",
            "PR-03",
            ["reporting_month", "material_code", "mekanisme", "program_status"],
        ),
        "promo_material_count": (
            "COUNT(DISTINCT sat_promo_material_december.material_code)",
            "PR-02",
            ["reporting_month", "mekanisme", "program_status"],
        ),
    }
    for name, (expression, metric_id, allowed_dimensions) in expected.items():
        metric = metrics[name]
        assert metric["expression"]["dialects"][0]["expression"] == expression
        extension = next(
            item for item in metric["custom_extensions"]
            if item["vendor_name"] == "TEMPO"
        )
        config = json.loads(extension["data"])
        assert config["metric_id"] == metric_id
        assert config["base_dataset"] == "sat_promo_material_december"
        assert config["allowed_dimensions"] == allowed_dimensions
        assert config["unit_format"] == "count"
        assert config["governance_status"] == "approved_candidate_with_caveat"
        assert config["business_approval_status"] == "pending_business_confirmation"

    assert "promo_active_count" not in metrics
    assert model["relationships"] == []
