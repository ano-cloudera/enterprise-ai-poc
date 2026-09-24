# TEMPO Impala + Apache Ossie Runbook

This runbook deploys the additive real-data profile without replacing the
existing `tempo_scan` synthetic foundation.

## 1. Safety boundary

Default behavior remains:

```text
PROJECT_ID=tempo_scan
DATA_BACKEND=duckdb
SEMANTIC_EXECUTION_MODE=legacy
```

Real-data mode is explicitly enabled with:

```text
PROJECT_ID=tempo_scan_impala
DATA_BACKEND=impala
SEMANTIC_EXECUTION_MODE=ossie
```

Rollback requires restoring the three default values and restarting the backend.
No existing tables, fixtures, semantic YAML, or frontend components are deleted.

## 2. CAI Workbench prerequisites

- Python 3.10 or 3.11
- Network access to the Impala coordinator
- Impala credentials/auth mechanism configured as CAI secrets
- Gold semantic views and metric catalog deployed
- Agent Studio only if custom tools are enabled

Install the backend plus Impala dependencies in a project-local environment:

```bash
python3 -m venv .venv
PIP_USER=false .venv/bin/pip install -r backend/requirements-impala.txt
```

Apache Ossie itself is a YAML/JSON specification. No standalone Ossie server or
database is required.

## 3. Required Impala objects

```text
gold.rpt_sap_monthly_executive_semantic
gold.rpt_sap_material_month_semantic
gold.rpt_service_level_material_month_semantic
gold.rpt_sap_customer_reconciliation_semantic
gold.rpt_sales_office_performance_semantic
gold.rpt_semantic_metric_catalog
```

Source-controlled DDL and audit SQL live under `datasets/audit/`.

## 4. Environment variables

```bash
export PROJECT_ID=tempo_scan_impala
export DATA_BACKEND=impala
export SEMANTIC_EXECUTION_MODE=ossie
export OSSIE_PROJECT_ID=tempo_scan_impala
export OSSIE_MAX_ROWS=200

export IMPALA_HOST=<impala-coordinator>
export IMPALA_PORT=21050
export IMPALA_DATABASE=gold
export IMPALA_AUTH_MECHANISM=PLAIN
export IMPALA_USER=<secret>
export IMPALA_PASSWORD=<secret>
export IMPALA_USE_SSL=false
```

Use the environment-specific authentication mechanism and SSL settings supplied
by the CDP administrator. Never commit credentials.

## 5. Offline contract validation

```bash
PYTHONPATH=backend .venv/bin/python scripts/validate_tempo_impala_contract.py
```

Expected:

```text
datasets=5 metrics=28 golden_questions=31
TEMPO Impala/Ossie contract validation PASSED
warnings=26
```

Warnings represent candidate metrics pending TEMPO business confirmation.

Validate against the current Apache Ossie schema:

```bash
python runtime/apache-ossie-schema/validation/validate.py \
  projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml \
  --schema runtime/apache-ossie-schema/core-spec/ossie-schema.json
```

## 6. Live read-only acceptance

```bash
PYTHONPATH=backend .venv/bin/python scripts/validate_tempo_impala_live.py
```

This checks:

- Q4 Gross Sales baseline
- monthly Fill Rate baseline
- Material 360 query
- Sales Office query
- shared-customer reconciliation query

The script submits only structured governed requests. It does not accept free
SQL and does not write to Impala.

## 7. Backend startup

Use the existing backend launcher after environment variables are set:

```bash
./scripts/run-cai-backend.sh
```

Check:

```text
GET /api/health
GET /api/deployment/readiness
GET /api/semantic/status
GET /api/semantic/capabilities
```

`/api/semantic/query` rejects execution unless both Ossie mode and Impala are
enabled.

## 8. UI behavior

With semantic mode enabled:

- Ask AI shows governed Q4 capabilities and real-data suggested questions.
- Dashboard shows Gross Sales, Fill Rate, top material, Sales Office ranking,
  Material ranking, and Sell-In/Sell-Out context.
- Forecast, weather, and market claims are hidden.
- Q4-only, shared-customer-only, proxy, and pending-approval caveats are shown.

Legacy mode continues to render the original synthetic experience.

## 9. Rollback

Set:

```text
PROJECT_ID=tempo_scan
DATA_BACKEND=duckdb
SEMANTIC_EXECUTION_MODE=legacy
```

Restart the backend and frontend. No code or data rollback is required because
the new profile is additive.

