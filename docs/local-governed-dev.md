# Local governed Ask AI (DuckDB sample, no Impala)

Use when **Ingram Impala is down** but you still need the full **governed OSSIE path** + Analysis Workspace (not the exploratory `backend-test` agent).

## What you get

- Same LangGraph resolver, SQL validator, analyst LLM, and UI as production.
- **1,000 synthetic rows per `gold.*` table** (column names from repo DDL + OSSIE; values are fake).
- Numbers are **for development only**, not official Tempo KPIs.

## Schema (1:1 column names with Impala/OSSIE views)

Column lists live in `backend/data/local_gold_view_schemas.yaml`, generated from repo `CREATE VIEW` DDL (`datasets/audit/`, `datasets/gold/`) plus OSSIE field fallback. Regenerate after OSSIE or Gold DDL changes:

```bash
PYTHONPATH=backend python backend/scripts/build_local_gold_schemas.py
```

Contract vs OSSIE rename map (same physical view on cluster): `rpt_sat_dc_month` ← `rpt_sat_idm_dc_month`, `corr_b2b_sat_branch_month` ← `corr_b2b_satidm_branch_month`, `corr_sat_dc_oos_material_month` ← `corr_satidm_oos_material_month`.

## One-time seed

```bash
# repo root, venv active
pip install duckdb   # or pip install -r backend/requirements.txt
PYTHONPATH=backend python backend/scripts/build_local_gold_schemas.py   # if yaml stale
PYTHONPATH=backend python backend/scripts/seed_local_gold_duckdb.py
# → backend/runtime/tempo_gold_local.duckdb
```

Optional path argument:

```bash
PYTHONPATH=backend-dev python backend-dev/scripts/seed_local_gold_duckdb.py backend-dev/runtime/tempo_gold_local.duckdb
```

Re-run the seed anytime to reset data (file is recreated).

## Run backend + frontend

**Production tree (`make dev` path):** in repo `.env` (or export):

```bash
DATA_BACKEND=duckdb
DUCKDB_PATH=backend/runtime/tempo_gold_local.duckdb
# LLM still required (GEMINI_* or QWEN_* / mock)
LLM_MODE=mock   # or remote with keys
```

```bash
make dev   # :8000 + :3000
```

**Pilot stack (`frontend-dev` + `backend-dev`):**

```bash
DEV_DATA_BACKEND=duckdb ./scripts/run-dev-stack.sh
# seeds backend-dev/runtime/tempo_gold_local.duckdb if missing, skips Impala preflight
```

## vs `backend-test`

| | Governed DuckDB (this doc) | `backend-test` |
|--|---------------------------|----------------|
| Resolver | OSSIE / deterministic | LLM writes SQL |
| Data | `gold.*` sample | `silver.*` sample |
| Workspace Query tab SQL | Same as Impala path | Different contract |
| Port | 8000 / 8001 with dev stack | 8001 only |

## Limitations

- Synthetic values; edge-case metrics may return empty or odd ranks.
- Hive SQL is transpiled to DuckDB; exotic functions may fail (`DUCKDB_QUERY_FAILED`).
- When Ingram is back, set `DATA_BACKEND=impala` and restore Kerberos env.
