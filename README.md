# Enterprise AI PoC Foundation

Reusable Cloudera AI application foundation. Tempo Scan is the first project profile, but the core is intentionally reusable for other PoCs.

## Locked architecture v2

- Next.js + TypeScript + Tailwind frontend
- FastAPI backend
- LangGraph controlled orchestration, not CrewAI
- Qwen3.8-27B-AWQ served by the existing proven vLLM 0.29.0 CAI Application
- Configurable semantic YAML validated by Pydantic
- DuckDB for local development; governed read-only Trino for Cloudera Data Warehouse runtime
- SQL validation before execution, SELECT-only, allowlisted semantic objects, read-only credentials
- Shared conversational + dashboard state
- Structured response: `answer + data + chart_spec + ui_actions + metadata`
- Fixed UI action whitelist, never arbitrary JavaScript
- Guardrails AI as an additive input/output validation layer; deterministic SQL/security controls remain mandatory

## Controlled flow

```text
User Question
  -> Input Guardrail
  -> Intent Router
  -> Semantic Resolver
  -> SQL Generator
  -> SQL Validator
  -> Query Execution
  -> Result Checker
  -> Qwen Analysis
  -> Visualization Planner
  -> UI Action Generator
  -> Output Guardrail
  -> Structured Response
```

The graph has bounded retry only. There is no unrestricted autonomous loop and no database write path.

## AI-driven dashboard behavior

The backend can return allowlisted declarative actions such as:

- `SET_FILTER`
- `SET_DATE_RANGE`
- `CHANGE_METRIC`
- `CHANGE_DIMENSION`
- `RENDER_CHART`
- `SHOW_TABLE`
- `HIGHLIGHT_CARD`
- `RESET_FILTER`

The frontend executes these actions. The LLM never emits code to control the browser.

## Repository layout

| Path | Role |
|------|------|
| `backend/` | FastAPI + LangGraph Ask AI, OSSIE semantic layer, Impala execution |
| `frontend/` | Next.js chat UI (proxies `/api/*` to the backend) |
| `scripts/` | Local dev, CAI shell helpers, UAT/eval runners |
| `docs/` | Architecture, API contract, **Cloudera AI deployment** |
| `projects/tempo_scan_impala/` | OSSIE YAML, golden questions, Agent Studio assets |

## Run locally

**Prerequisites:** Python **3.10**, Node.js **20+**, `npm`. Ask AI against real TEMPO data needs **Impala** credentials in `.env` (`DATA_BACKEND=impala`, `IMPALA_*`, `PROJECT_ID=tempo_scan_impala`). Use `LLM_MODE=mock` to develop without calling Qwen.

**One-time setup** (repo root):

```bash
cp .env.example .env
# Edit .env: IMPALA_*, optional QWEN_* if LLM_MODE=remote
bash scripts/setup-local.sh
```

`setup-local.sh` creates `.venv`, installs `backend/requirements.txt` + `backend/requirements-impala.txt`, generates DuckDB sample data (forecast/legacy tools), and runs `npm install` in `frontend/`.

**Start frontend + backend together:**

```bash
make dev
```

Or run separately:

```bash
make api   # FastAPI → http://127.0.0.1:8000/docs
make web   # Next.js → http://127.0.0.1:3000
```

**Use the repo venv for backend commands** (system Python may lack `langgraph`):

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Tests:**

```bash
make test
# or targeted:
cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest tests/ -q
```

**Multi-turn UAT harness** (backend must be up on `:8000`):

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python scripts/run_uat_domain_5x5_followup.py --domain=promo
PYTHONPATH=. ../.venv/bin/python scripts/merge_uat_domain_5x5_followup_reports.py
```

**Common `.env` modes**

| Goal | Typical settings |
|------|------------------|
| Offline UI/API smoke | `LLM_MODE=mock`, minimal Impala if you only hit health routes |
| Full governed Ask AI | `DATA_BACKEND=impala`, `SEMANTIC_EXECUTION_MODE=ossie`, valid `IMPALA_*` |
| Local LLM via deployed Qwen | `LLM_MODE=remote`, `QWEN_BASE_URL=https://<qwen-cai-app>/v1`, `QWEN_MODEL=Qwen3.8-27B-AWQ`, `QWEN_API_TOKEN=…` |

Qwen is used after governed SQL execution for narrative/chart planning; SQL remains deterministic and validated.

**Trino (optional CDW path):** after configuring `TRINO_*` in `.env`:

```bash
.venv/bin/python scripts/test_trino_connection.py
```

## Run on Cloudera AI Applications (CAI)

Production shape is **split applications** (same pattern as the proven Qwen vLLM app): one CAI Application for the **backend**, one for the **frontend**, plus the existing **Qwen** model Application. Do not replace the running Qwen app from `model-serving/reference-vllm/` unless you have a separate reason.

### CAI entrypoints (set in Application → Script)

| Application | Script field | Binds |
|-------------|--------------|--------|
| Tempo backend | `backend/app_cai_backend.py` | `127.0.0.1` + `CDSW_APP_PORT` |
| Tempo frontend | `frontend/app_cai_frontend.py` | `127.0.0.1` + `CDSW_APP_PORT` |

Both scripts resolve the checkout from `CDSW_PROJECT_DIR`, bootstrap their own venv (backend) or Node/`npm ci` + `next build` (frontend), and keep child process logs visible in **Application Logs**. Use **`CDSW_APP_PORT`** (injected by CAI); do not hardcode public ports or bind `0.0.0.0` in the `.py` entrypoints.

**Dry-run locally** (prints resolved cwd/command without starting servers):

```bash
CAI_DRY_RUN=1 python backend/app_cai_backend.py
CAI_DRY_RUN=1 NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000 python frontend/app_cai_frontend.py
```

(`frontend/app_cai_frontend.py` accepts `NEXT_PUBLIC_BACKEND_URL` or `NEXT_PUBLIC_BACKEND_API_URL`.)

### Deploy order (summary)

1. Ensure the **Qwen** CAI Application is healthy; note its OpenAI-compatible base URL (`…/v1`).
2. Create **Backend** Application → Script: `backend/app_cai_backend.py`. Set secrets/env: `APP_ENV=production`, `DATA_BACKEND=impala`, `LLM_MODE=remote`, `QWEN_*`, `IMPALA_*` / Kerberos profile per cluster, `PROJECT_ID=tempo_scan_impala`, `CORS_ORIGINS` (frontend URL once known). Validate: `curl $BACKEND_URL/api/health`.
3. Create **Frontend** Application → Script: `frontend/app_cai_frontend.py`. Set **`NEXT_PUBLIC_BACKEND_API_URL`** to the backend’s **public** URL (required at build time).
4. Open the frontend public URL; the browser calls same-origin `/api/*`, proxied server-side to the backend.

**Shell helpers** (local terminal only — bind differently than CAI; use the `.py` scripts in the CAI console):

```bash
bash scripts/run-cai-backend.sh
bash scripts/run-cai-frontend.sh   # requires NEXT_PUBLIC_BACKEND_API_URL
```

Full variable tables, Impala Kerberos vs LDAP notes, LiteLLM/Agent Studio options, and troubleshooting: **`docs/cloudera-ai-deployment.md`**. Snapshot config template for migrating environments: **`docs/cai-application-deployment-config.md`**.

## Synthetic Tempo bootstrap

Trino demo loading is an explicit operator workflow using a separate loader identity. Preview the exact target and row counts without connecting:

```bash
TRINO_LOADER_CATALOG=<catalog> \
TRINO_LOADER_SCHEMA=<schema> \
.venv/bin/python scripts/bootstrap_trino_demo.py --dry-run
```

With dedicated loader credentials configured:

```bash
.venv/bin/python scripts/bootstrap_trino_demo.py
.venv/bin/python scripts/validate_trino_demo_data.py
```

After validation, configure the separate SELECT-only `TRINO_*` runtime identity and use `DATA_BACKEND=trino make dev`. See `docs/trino-demo-data.md` for the permission boundary and complete workflow.

## Offline forecasting

Milestone 6A adds one-month total/region/product/channel forecasts without online ML inference:

```bash
.venv/bin/python scripts/train_forecast.py
.venv/bin/python scripts/generate_forecast.py
```

The scripts evaluate XGBoost against lag-1 chronologically and promote the better model. The application only queries persisted `commercial_sales_forecast` rows through the governed Forecast Tool. Missing forecasts return `FORECAST_NOT_AVAILABLE` and are never estimated by Qwen. See `docs/forecasting.md`.

## Key docs

- `docs/README.md` — documentation index (active vs archive vs needs update)
- `docs/cloudera-ai-deployment.md` — CAI split deploy, env vars, health checks
- `docs/tempo-impala-ossie-runbook.md` — Impala/OSSIE governed mode
- `docs/data-enhancement-views.md` — optional Gold views
- `docs/cai-application-deployment-config.md` — replicate Applications in a new workspace
- `docs/architecture.md`
- `docs/api-contract-v2.md`
- `docs/repository-structure-v2.md`
- `docs/development-sequence-v2.md`
- `docs/semantic-layer.md`
- `docs/nl-to-sql.md`
- `docs/golden-questions.md`
- `docs/qwen-integration.md`
- `docs/health.md`
- `docs/trino-demo-data.md`
- `docs/forecasting.md`
- `PROJECT_STATE.md` — current milestone / UAT checkpoint
- `PROJECT_STATUS.md`

## Important boundary

`model-serving/reference-vllm/` is a frozen reference snapshot of the already proven model-serving implementation. Do not rebuild or replace the running Qwen/vLLM CAI Application from this folder unless there is a separate technical reason.
