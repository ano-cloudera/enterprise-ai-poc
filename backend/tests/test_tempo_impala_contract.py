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
    assert payload["datasets"] == 14
    assert payload["metrics"] == 39
    assert payload["golden_questions"] >= 50


def test_tempo_impala_model_uses_only_audited_semantic_views() -> None:
    model = _load(MODEL_PATH)
    sources = {dataset["source"] for dataset in model["datasets"]}
    assert sources == {
        "gold.rpt_sap_monthly_executive_semantic",
        "gold.rpt_sap_material_month_semantic",
        "gold.rpt_service_level_material_month_semantic",
        "gold.rpt_sap_customer_reconciliation_semantic",
        "gold.rpt_sales_office_performance_semantic",
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

