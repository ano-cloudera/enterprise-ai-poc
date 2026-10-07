#!/usr/bin/env python3
"""
Audit OSSIE EXPECTED_SOURCES on live Impala (Ingram / any profile via .env).

Usage:
  export IMPALA_CREDENTIAL_PROFILE=ingram
  export KRB5_CONFIG=backend/runtime/krb5-ingram.conf   # off-cluster Mac only
  kinit principal@IMID.LOCAL                             # if GSSAPI

  .venv/bin/python scripts/audit_gold_ingram.py
  .venv/bin/python scripts/audit_gold_ingram.py --json

Deploy gaps (often on AWS first, missing on Ingram):
  backend/scripts/deploy_gold_enhancement_views.py
  docs/data-enhancement-views.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from validate_tempo_impala_contract import EXPECTED_SOURCES  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.impala_backend import ImpalaBackend, is_impala_configured  # noqa: E402

# OSSIE source → where to find CREATE VIEW DDL in repo (operator hint).
DEPLOY_HINTS: dict[str, str] = {
    "gold.rpt_sap_monthly_executive_semantic": "datasets/audit/05–07 + migration bundle on cluster",
    "gold.rpt_sap_material_month_semantic": "datasets/gold/ + datasets/audit/07_*",
    "gold.rpt_service_level_material_month_semantic": "datasets/audit/08_*",
    "gold.rpt_sap_customer_reconciliation_semantic": "datasets/audit/09_*",
    "gold.rpt_sales_office_performance_semantic": "datasets/audit/10_*",
    "gold.corr_b2b_branch_estore_month": "journey / migration gold bundle",
    "gold.corr_b2b_material_plu": "journey / migration gold bundle",
    "gold.corr_stock_tempo_month_seta": "journey / migration gold bundle",
    "gold.rpt_sat_dc_month": "journey / migration gold bundle",
    "gold.rpt_sat_oos_material_month": "journey / migration gold bundle",
    "gold.corr_stock_tempo_sales_material_month": "journey / migration gold bundle",
    "gold.corr_sales_b2b_material_month": "journey / migration gold bundle",
    "gold.corr_b2b_sat_branch_month": "journey / migration gold bundle",
    "gold.corr_sat_dc_oos_material_month": "journey / migration gold bundle",
    "gold.rpt_sat_promo_material_december_semantic": "datasets/gold/23_rpt_sat_promo_material_december_semantic.sql",
    "gold.rpt_sat_promo_material_uplift": "SAT promo uplift (cluster migration)",
    "gold.rpt_sap_customer_material_month_semantic": "datasets/gold/24_rpt_sap_customer_office_material_month_semantic.sql",
    "gold.rpt_sap_sales_office_material_month_semantic": "datasets/gold/24_rpt_sap_customer_office_material_month_semantic.sql",
    "gold.corr_b2b_customer_branch_estore_month": "datasets/gold/25a_*.sql / 25_*",
    "gold.corr_b2b_customer_material_plu_month": "datasets/gold/25b_*.sql / 25_*",
    "gold.corr_b2b_branch_material_month": "datasets/gold/01_corr_b2b_branch_material_month.sql (deploy_gold_enhancement_views.py)",
    "gold.corr_service_sales_office_material_month": "datasets/gold/26_rpt_service_level_sales_office_semantic.sql",
    "gold.rpt_sat_promo_b2b_sellout_uplift": "datasets/gold/02_rpt_sat_promo_b2b_sellout_uplift.sql (enhancement deploy)",
    "gold.corr_service_sales_office_cust_group_material_month": "datasets/gold/03_corr_service_sales_office_cust_group_material_month.sql",
}


def _classify_error(message: str) -> str:
    lower = message.casefold()
    if "gsserror" in lower or "no credential" in lower or "401" in lower or "403" in lower:
        return "kerberos_auth"
    if "analysisexception" in lower or "could not resolve" in lower or "table/view not found" in lower:
        return "missing_view"
    if "authorization" in lower or "permission" in lower:
        return "permission"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-empty", action="store_true", help="Do not fail on COUNT(*)=0")
    args = parser.parse_args()

    get_settings.cache_clear()
    settings = get_settings()
    if not is_impala_configured(settings):
        payload = {"status": "misconfigured", "host": settings.impala_host, "auth": settings.impala_auth_mechanism}
        print(json.dumps(payload, indent=2) if args.json else "Impala not configured in Settings/.env")
        return 2

    backend = ImpalaBackend(settings)
    missing: list[str] = []
    empty: list[str] = []
    ok: list[str] = []
    auth_block = False
    results: dict[str, dict] = {}

    for source in sorted(EXPECTED_SOURCES):
        try:
            rows = backend.query(f"SELECT COUNT(*) AS row_count FROM {source}")
            count = int(rows[0]["row_count"]) if rows else -1
            results[source] = {"row_count": count, "status": "ok" if count > 0 else "empty"}
            if count > 0:
                ok.append(source)
            elif args.allow_empty:
                empty.append(source)
            else:
                empty.append(source)
        except Exception as exc:
            msg = str(exc)
            kind = _classify_error(msg)
            results[source] = {"status": kind, "error": msg[:500]}
            if kind == "kerberos_auth":
                auth_block = True
            missing.append(source)

    failures = missing + ([] if args.allow_empty else empty)
    payload = {
        "profile": settings.impala_credential_profile,
        "host": settings.impala_host,
        "auth": settings.impala_auth_mechanism,
        "views_checked": len(EXPECTED_SOURCES),
        "ok_with_rows": len(ok),
        "empty": len(empty),
        "missing_or_error": len(missing),
        "auth_blocked": auth_block,
        "status": "passed" if not failures and not auth_block else "failed",
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Impala profile={settings.impala_credential_profile} host={settings.impala_host} auth={settings.impala_auth_mechanism}")
        print(f"Checked {len(EXPECTED_SOURCES)} OSSIE gold sources: {len(ok)} with rows, {len(empty)} empty, {len(missing)} errors")
        if auth_block:
            print("\n*** Kerberos/GSSAPI failure — fix CAI ticket/keytab before blaming missing views ***")
            print("    See backend/requirements-impala.txt (kerberos package) + cluster keytab for tempo-backend Application.")
        if missing:
            print("\nMISSING / ERROR:")
            for src in missing:
                hint = DEPLOY_HINTS.get(src, "see datasets/gold + datasets/audit + cluster migration SQL")
                err = results[src].get("error", "")[:120]
                print(f"  - {src}")
                print(f"      hint: {hint}")
                if err:
                    print(f"      error: {err}")
        if empty:
            print("\nEMPTY (exists but COUNT=0):")
            for src in empty:
                print(f"  - {src}")
        if not missing and not empty:
            print("\nAll views queryable with row_count > 0.")
        elif not missing and empty and args.allow_empty:
            print("\nAll views exist; some empty (--allow-empty).")

        print("\nDeploy enhancement views (often added on AWS test first):")
        print("  cd backend && PYTHONPATH=. python scripts/deploy_gold_enhancement_views.py")

    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
