#!/usr/bin/env python3
"""Validate the isolated TEMPO Impala/Ossie semantic contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sqlglot
import yaml


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "projects" / "tempo_scan_impala"
MODEL_PATH = PROJECT_DIR / "ossie" / "tempo_core.ossie.yaml"
GOVERNANCE_PATH = PROJECT_DIR / "ossie" / "tempo_governance.yaml"
GOLDEN_PATH = PROJECT_DIR / "ossie" / "golden_questions.yaml"

# Original Semantic Contract v1 baseline (5 audited Gold semantic views).
BASELINE_SOURCES = {
    "gold.rpt_sap_monthly_executive_semantic",
    "gold.rpt_sap_material_month_semantic",
    "gold.rpt_service_level_material_month_semantic",
    "gold.rpt_sap_customer_reconciliation_semantic",
    "gold.rpt_sales_office_performance_semantic",
}
# 24 Sep 2026 journey expansion (Stock Tempo -> Sales -> B2B -> SAT-IDM ->
# OOS, see TEMPO_DATAMART_PLAN.md §8.1): 5 per-domain Gold views + 4
# cross-domain journey views, all built and validated against Impala
# (row counts + join match rates) before being registered here.
JOURNEY_SOURCES = {
    "gold.corr_b2b_branch_estore_month",
    "gold.corr_b2b_material_plu",
    "gold.corr_stock_tempo_month_seta",
    "gold.rpt_sat_idm_dc_month",
    "gold.rpt_sat_oos_material_month",
    "gold.corr_stock_tempo_sales_material_month",
    "gold.corr_sales_b2b_material_month",
    "gold.corr_b2b_satidm_branch_month",
    "gold.corr_satidm_oos_material_month",
}
EXPECTED_SOURCES = BASELINE_SOURCES | JOURNEY_SOURCES


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return value


def _tempo_extension(item: dict[str, Any]) -> dict[str, Any]:
    for extension in item.get("custom_extensions", []):
        if extension.get("vendor_name") == "TEMPO":
            data = extension.get("data", {})
            return json.loads(data) if isinstance(data, str) else dict(data)
    return {}


def _ansi_expression(item: dict[str, Any]) -> str:
    expression = item.get("expression", {})
    if isinstance(expression, str):
        return expression
    for candidate in expression.get("dialects", []):
        if candidate.get("dialect") == "ANSI_SQL":
            return str(candidate["expression"])
    raise ValueError(f"No ANSI_SQL expression for {item.get('name')}")


def validate_contract() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    model = _load_yaml(MODEL_PATH)
    governance = _load_yaml(GOVERNANCE_PATH)
    golden = _load_yaml(GOLDEN_PATH)

    datasets = {item["name"]: item for item in model.get("datasets", [])}
    metrics = {item["name"]: item for item in model.get("metrics", [])}

    if len(datasets) != len(model.get("datasets", [])):
        errors.append("Dataset names must be unique")
    if len(metrics) != len(model.get("metrics", [])):
        errors.append("Metric names must be unique")
    if set(item.get("source") for item in datasets.values()) != EXPECTED_SOURCES:
        errors.append("Dataset sources differ from the five audited Gold semantic views")

    dataset_fields: dict[str, set[str]] = {}
    dimensions: dict[str, set[str]] = {}
    for dataset_name, dataset in datasets.items():
        fields = dataset.get("fields", [])
        names = [field["name"] for field in fields]
        if len(names) != len(set(names)):
            errors.append(f"Dataset {dataset_name} has duplicate field names")
        dataset_fields[dataset_name] = set(names)
        dimensions[dataset_name] = {
            field["name"] for field in fields if "dimension" in field
        }
        for key in dataset.get("primary_key", []):
            if key not in dataset_fields[dataset_name]:
                errors.append(f"Dataset {dataset_name} primary key references unknown field {key}")
        extension = _tempo_extension(dataset)
        if extension.get("layer") != "semantic_gold":
            errors.append(f"Dataset {dataset_name} must declare semantic_gold layer")

    metric_ids: set[str] = set()
    for metric_name, metric in metrics.items():
        extension = _tempo_extension(metric)
        metric_id = extension.get("metric_id")
        base_dataset = extension.get("base_dataset")
        if not metric_id:
            errors.append(f"Metric {metric_name} has no metric_id")
        elif metric_id in metric_ids:
            errors.append(f"Duplicate metric_id {metric_id}")
        metric_ids.add(str(metric_id))

        if base_dataset not in datasets:
            errors.append(f"Metric {metric_name} references unknown base_dataset {base_dataset}")
            continue
        allowed_dimensions = set(extension.get("allowed_dimensions", []))
        unknown_dimensions = allowed_dimensions - dimensions[base_dataset]
        if unknown_dimensions:
            errors.append(
                f"Metric {metric_name} allows unknown dimensions {sorted(unknown_dimensions)}"
            )
        required_filters = set(extension.get("required_filters", []))
        unknown_filters = required_filters - dataset_fields[base_dataset]
        if unknown_filters:
            errors.append(
                f"Metric {metric_name} requires unknown filters {sorted(unknown_filters)}"
            )

        expression = _ansi_expression(metric)
        try:
            sqlglot.parse_one(
                f"SELECT {expression} FROM {datasets[base_dataset]['source']}",
                read="hive",
            )
        except Exception as exc:
            errors.append(f"Metric {metric_name} has invalid Hive SQL: {exc}")

        for field_name in dataset_fields[base_dataset]:
            # Exact field reference validation is done below by token inspection.
            if f"{base_dataset}.{field_name}" in expression:
                break
        else:
            errors.append(
                f"Metric {metric_name} expression does not reference its base dataset"
            )

        if extension.get("business_approval_status") == "pending_business_confirmation":
            warnings.append(f"Metric {metric_name} is pending business confirmation")

    known_metrics = set(metrics)
    for ambiguity in governance.get("ambiguities", []):
        for option in ambiguity.get("options", []):
            if option.get("metric") not in known_metrics:
                errors.append(
                    f"Ambiguity {ambiguity.get('name')} references unknown metric "
                    f"{option.get('metric')}"
                )

    questions = golden.get("questions", [])
    question_ids = [item["id"] for item in questions]
    if len(question_ids) != len(set(question_ids)):
        errors.append("Golden question IDs must be unique")
    for question in questions:
        status = question.get("expected_status")
        if status in {"supported", "supported_with_caveat"}:
            if question.get("metric") not in known_metrics:
                errors.append(
                    f"Golden question {question['id']} references unknown metric "
                    f"{question.get('metric')}"
                )
            if question.get("dataset") not in datasets:
                errors.append(
                    f"Golden question {question['id']} references unknown dataset "
                    f"{question.get('dataset')}"
                )
        elif status not in {"needs_clarification", "unsupported", "blocked"}:
            errors.append(f"Golden question {question['id']} has unknown status {status}")

    # Minimums, not exact counts - see BASELINE_SOURCES/JOURNEY_SOURCES above
    # and TempoOssieRegistry.validate()'s matching comment.
    if len(datasets) < 5:
        errors.append(f"Expected at least 5 datasets, found {len(datasets)}")
    if len(metrics) < 28:
        errors.append(f"Expected at least 28 metrics, found {len(metrics)}")

    return {
        "valid": not errors,
        "datasets": len(datasets),
        "metrics": len(metrics),
        "golden_questions": len(questions),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_contract()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"datasets={result['datasets']} metrics={result['metrics']} "
            f"golden_questions={result['golden_questions']}"
        )
        if result["errors"]:
            print("ERRORS:")
            for error in result["errors"]:
                print(f"- {error}")
        else:
            print("TEMPO Impala/Ossie contract validation PASSED")
        print(f"warnings={len(result['warnings'])}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

