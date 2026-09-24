#!/usr/bin/env python3
"""Read-only live acceptance checks for the opt-in TEMPO Impala/Ossie profile."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.ossie.service import OssieQueryRequest, get_tempo_ossie_service  # noqa: E402


EXPECTED_Q4_GROSS_SALES = 384_186_578_707.30
EXPECTED_FILL_RATES = {
    202410: 0.755831,
    202411: 0.779350,
    202412: 0.795198,
}


def _metric(metric: str, dimensions: list[str]) -> list[dict]:
    return get_tempo_ossie_service().execute_query(
        OssieQueryRequest(
            metric=metric,
            dimensions=dimensions,
            start_calmonth=202410 if "calmonth" in dimensions else None,
            end_calmonth=202412 if "calmonth" in dimensions else None,
            limit=50,
        )
    )["rows"]


def main() -> int:
    settings = get_settings()
    failures: list[str] = []
    if settings.semantic_execution_mode != "ossie":
        failures.append("SEMANTIC_EXECUTION_MODE must be ossie")
    if settings.data_backend != "impala":
        failures.append("DATA_BACKEND must be impala")
    if failures:
        print(json.dumps({"status": "misconfigured", "failures": failures}, indent=2))
        return 2

    gross_rows = _metric("gross_billing_value", [])
    gross_sales = float(gross_rows[0]["metric_value"])
    if abs(gross_sales - EXPECTED_Q4_GROSS_SALES) > 1.0:
        failures.append(
            f"Gross Sales mismatch: expected {EXPECTED_Q4_GROSS_SALES}, got {gross_sales}"
        )

    fill_rows = _metric("company_fill_rate", ["calmonth"])
    actual_fill = {
        int(row["calmonth"]): round(float(row["metric_value"]), 6)
        for row in fill_rows
    }
    if actual_fill != EXPECTED_FILL_RATES:
        failures.append(
            f"Fill Rate mismatch: expected {EXPECTED_FILL_RATES}, got {actual_fill}"
        )

    material_rows = _metric("material_sell_in_value", ["material"])
    if not material_rows:
        failures.append("Material 360 returned no governed Sell-In rows")

    office_rows = _metric("sales_office_sell_in_value", ["sales_office"])
    if not office_rows:
        failures.append("Sales Office semantic view returned no rows")

    customer_rows = _metric(
        "sell_out_to_sell_in_value_ratio",
        ["calmonth", "customer"],
    )
    if not customer_rows:
        failures.append("Customer reconciliation returned no rows")

    payload = {
        "status": "passed" if not failures else "failed",
        "model": get_tempo_ossie_service().status(),
        "checks": {
            "q4_gross_sales": gross_sales,
            "monthly_fill_rate": actual_fill,
            "material_rows_sampled": len(material_rows),
            "office_rows_sampled": len(office_rows),
            "customer_rows_sampled": len(customer_rows),
        },
        "failures": failures,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

