#!/usr/bin/env python3
"""Runs 5 representative TEMPO business questions through the same governed
query path Ask AI uses (OssieQueryRequest -> get_tempo_ossie_service()), and
prints the exact SQL executed plus the top rows - so the numbers shown in
the UI can be audited against the governed query directly, without trusting
the LLM's phrasing of them.

Usage (from the repo root, with the same Impala/Ossie env vars set as the
backend):
    PYTHONPATH=backend .venv/bin/python scripts/audit_tempo_sample_questions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.ossie.service import OssieQueryRequest, get_tempo_ossie_service  # noqa: E402


SAMPLE_QUESTIONS = [
    {
        "id": "exec_gross_sales_q4",
        "question": "Berapa Gross Sales Tempo selama Q4 2024?",
        "request": OssieQueryRequest(metric="gross_billing_value", dimensions=[]),
    },
    {
        "id": "material_top_sell_in",
        "question": "Material mana dengan nilai Sell-In terbesar pada Q4?",
        "request": OssieQueryRequest(
            metric="material_sell_in_value", dimensions=["material"], limit=5
        ),
    },
    {
        "id": "exec_fill_rate",
        "question": "Bagaimana Fill Rate per bulan?",
        "request": OssieQueryRequest(
            metric="company_fill_rate", dimensions=["calmonth"], order="asc"
        ),
    },
    {
        "id": "office_sell_in",
        "question": "Sales office mana dengan nilai Sell-In Q4 tertinggi?",
        "request": OssieQueryRequest(
            metric="sales_office_sell_in_value", dimensions=["sales_office"], limit=5
        ),
    },
    {
        "id": "customer_reconciliation",
        "question": "Customer mana dengan gap Sell-In dan Sell-Out terbesar?",
        "request": OssieQueryRequest(
            metric="sell_in_minus_sell_out_value", dimensions=["customer"], limit=5
        ),
    },
]


def main() -> int:
    settings = get_settings()
    if settings.semantic_execution_mode != "ossie" or settings.data_backend != "impala":
        print(json.dumps({
            "status": "misconfigured",
            "detail": "Set SEMANTIC_EXECUTION_MODE=ossie and DATA_BACKEND=impala "
                      "(plus Impala credentials) before running this audit.",
        }, indent=2))
        return 2

    service = get_tempo_ossie_service()
    results = []
    exit_code = 0

    for item in SAMPLE_QUESTIONS:
        try:
            outcome = service.execute_query(item["request"])
            results.append({
                "id": item["id"],
                "question": item["question"],
                "status": "ok",
                "sql": outcome["sql"],
                "governance_status": outcome["semantic_plan"]["governance_status"],
                "business_approval_status": outcome["semantic_plan"]["business_approval_status"],
                "row_count": outcome["row_count"],
                "top_rows": outcome["rows"][:5],
            })
        except Exception as exc:  # noqa: BLE001 - audit script, show any failure
            exit_code = 1
            results.append({
                "id": item["id"],
                "question": item["question"],
                "status": "error",
                "error": str(exc),
            })

    print(json.dumps({"status": "ok" if exit_code == 0 else "failed", "results": results}, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
