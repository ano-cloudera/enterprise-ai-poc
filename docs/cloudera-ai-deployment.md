# Cloudera AI Deployment Guide

Operational guide for deploying the Tempo Scan Commercial Intelligence
Assistant to Cloudera AI (CAI). See [cai-deployment.md](cai-deployment.md)
for the original architecture direction; this document is the copy-paste
operator runbook for the **current approved architecture: three separate
CAI Applications.**

## 1. Architecture

```
User Browser
      |
      v
CAI Application #1 — Tempo Scan Frontend
Next.js production app
      |
      | HTTPS REST API (cross-origin, NEXT_PUBLIC_BACKEND_API_URL)
      v
CAI Application #2 — Tempo Scan Backend
FastAPI + LangGraph + semantic layer + forecast/weather/market tools
+ Mock External Market API (served internally, not a separate app)
+ DuckDB (initial deployment) / Trino (future, see §10)
      |
      | OpenAI-compatible API
      v
CAI Application #3 — Existing Qwen Model Serving (already running)
Qwen3.8-27B-AWQ via vLLM on NVIDIA L40S
(code: testing/vllm_testing/vllm/proxy.py)
```

**Only two applications are created in this milestone**: Tempo Scan
Frontend and Tempo Scan Backend. The Qwen application already exists — do
not redeploy or modify it. There is no fourth application for the Mock
Market API; it runs as an internal process inside the Backend Application.

Serper.dev and Open-Meteo are controlled, manual data-refresh sources
(`scripts/fetch_market_snapshot.py`, `scripts/fetch_weather_history.py`),
not runtime dependencies and not separate applications.

> A legacy single-application path also still exists for local all-in-one
> testing — see §11. It is **not** the deployment target anymore.

## 2. Prerequisites

- A Cloudera AI project with **two Application slots** available (Frontend,
  Backend).
- The existing Qwen/vLLM CAI Application already running, with its public
  URL known.
- Python 3.10 and Node.js 18+ available in the CAI runtime images.
- Network egress from the Backend Application to the Qwen Application's URL.
- No Trino/CDW credentials required for this milestone.

## 3. Environment variables

Copy `.env.example` as a starting point; set real values through each CAI
Application's own environment/secrets UI — never commit real secrets, and
never put a secret in a `NEXT_PUBLIC_*` variable (see §3.2).

### 3.1 Backend Application environment variables

| Variable | Required | Example | Secret? | Description |
| --- | --- | --- | --- | --- |
| `APP_ENV` | no | `production` | no | Deployment environment label |
| `CORS_ORIGINS` | **yes** | `https://tempo-frontend.cai.example` | no | Comma-separated list of allowed frontend origins. No wildcard in production. Set once the Frontend URL is known (§7) |
| `DATA_BACKEND` | no (default `duckdb`) | `duckdb` | no | `duckdb` for this milestone; `trino` later (§10) |
| `DUCKDB_PATH` | no | `runtime/tempo_scan.duckdb` | no | Relative to repo root |
| `LLM_MODE` | no (default `mock`) | `remote` | no | `mock` = offline deterministic; `remote` = calls Qwen |
| `QWEN_BASE_URL` | yes if `LLM_MODE=remote` | `https://qwen-model.ml-....cloudera.site/v1` | no (URL only) | Existing Qwen Application's public URL |
| `QWEN_MODEL` | yes if `LLM_MODE=remote` | `Qwen3.8-27B-AWQ` | no | Model name served by Qwen Application |
| `QWEN_API_TOKEN` | if Qwen requires auth | — | **yes** | Set via CAI secrets only |
| `MARKET_API_BASE_URL` | no | `http://127.0.0.1:8100` | no | Internal only — Mock Market API runs inside this same application |
| `SERPER_API_KEY` | no | — | **yes** | Only used by manual refresh scripts, not at runtime |
| `SERPER_ENABLED` | no (default `false`) | `false` | no | Keep `false` for normal startup |

### 3.2 Frontend Application environment variables

Everything here is inlined into the browser bundle at **build time** — do
not put secrets here.

| Variable | Required | Example | Secret? | Description |
| --- | --- | --- | --- | --- |
| `NEXT_PUBLIC_BACKEND_API_URL` | **yes** | `https://tempo-backend.cai.example` | no | Deployed Backend Application's public URL. No trailing slash needed |
| `NEXT_PUBLIC_APP_NAME` | no | `Commercial Intelligence` | no | Cosmetic |
| `NEXT_PUBLIC_CUSTOMER_NAME` | no | `Tempo Scan` | no | Cosmetic |

Never set `QWEN_API_TOKEN`, `SERPER_API_KEY`, `TRINO_PASSWORD`,
`TRINO_ACCESS_TOKEN`, or any database credential on the Frontend
Application. The frontend never talks to Qwen directly — only the Backend
does.

**Important**: because `NEXT_PUBLIC_*` values are baked in at build time,
changing `NEXT_PUBLIC_BACKEND_API_URL` requires rebuilding the frontend
(`frontend/app_cai_frontend.py` rebuilds by default every start — see §6).

Cloudera AI injects `CDSW_APP_PORT` into both applications at runtime — do
not set this yourself. Both entrypoints also accept `PORT` as a fallback for
local testing outside CAI.

## 4. Install dependencies (both applications)

`backend/app_cai_backend.py` **self-bootstraps its own virtualenv** at
`.venv` under the repo root on first start (creates it if missing, installs
`backend/requirements-lock.txt` into it, and re-installs only when the lock
file changes) — it does not assume the CAI Application's interpreter
already has the right packages. Manual install is only needed for local
development outside the entrypoint:

```bash
# Python (optional local dev convenience — the Backend entrypoint bootstraps
# its own venv automatically on CAI)
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-lock.txt

# Frontend (Frontend Application only — Next.js/npm, not bootstrapped automatically)
cd frontend && npm ci && cd ..
```

## 5. Verify required demo data exists (Backend Application only)

```bash
ls runtime/tempo_scan.duckdb || python3 scripts/generate_sample_data.py
```

`backend/app_cai_backend.py` also checks this and fails clearly if missing,
rather than silently regenerating data on every start.

## 6. Startup commands

Cloudera AI Applications run a **Python entrypoint file**, the same pattern
already proven by the existing Qwen Application
(`testing/vllm_testing/vllm/app.py`) — not a shell script. When creating
each Application in the CAI console, set its **Script** field to the
`app_cai_*.py` file below (not a `.sh` file).

Both entrypoints follow the CAI Application execution model: port
resolution is `CDSW_APP_PORT` → `PORT` → a local-testing default (CAI sets
`CDSW_APP_PORT` and its own reverse proxy handles external exposure), every
process binds `127.0.0.1` only — **never `0.0.0.0`** and never a hardcoded
externally-exposed port — and the checkout path is resolved from
`CDSW_PROJECT_DIR` rather than `__file__` (which CAI's interpreter
execution can leave unset or wrong).

**Backend Application** — Script: `backend/app_cai_backend.py`
```bash
python backend/app_cai_backend.py
```
Validates env (`DATA_BACKEND`, `LLM_MODE` + Qwen vars if remote, DuckDB
file presence, a resolvable port), starts the Mock External Market API as
an internal child process on `127.0.0.1:8100` (log-prefixed `[market-api]`)
and waits for its `/health`, then starts FastAPI bound to
`127.0.0.1:$CDSW_APP_PORT` (log-prefixed `[backend]`) and waits for
`/api/health`. Does **not** start the frontend. Fails loudly if any step
doesn't come up. Monitors both subprocesses and cleans them up on shutdown,
same as the Qwen app.py, with both children's stdout/stderr preserved so
failures show up in CAI's Application Logs.

**Frontend Application** — Script: `frontend/app_cai_frontend.py`
```bash
python frontend/app_cai_frontend.py
```
Validates `NEXT_PUBLIC_BACKEND_API_URL` is set and well-formed, builds the
production bundle (bakes the backend URL in), then starts `next start`
bound to `127.0.0.1:$CDSW_APP_PORT` (log-prefixed `[frontend]`). Does
**not** start the backend or the Mock Market API. Set `BUILD_SKIP=1` to
reuse an existing `.next` build instead of rebuilding (only when the
backend URL hasn't changed).

Neither entrypoint uses `npm run dev` or `uvicorn --reload`.

> Local testing convenience: `scripts/run-cai-backend.sh` and
> `scripts/run-cai-frontend.sh` (shell equivalents of the two `app_cai_*.py`
> files, binding `0.0.0.0` for plain local terminal use) still work for
> local testing outside CAI, but **the CAI Application console needs the
> `.py` entrypoints**, matching the platform's existing convention and
> binding rules.

## 7. Deployment order

1. Confirm the existing Qwen Application is running; note its public URL.
2. Deploy the **Backend** Application (Script: `backend/app_cai_backend.py`),
   with `LLM_MODE=remote`, `QWEN_BASE_URL`/`QWEN_MODEL` set to the Qwen
   Application above, and `CORS_ORIGINS` initially set to a placeholder (it
   will be corrected in step 8).
3. Validate the Backend directly: `curl $BACKEND_URL/api/health` and
   `curl $BACKEND_URL/api/deployment/readiness`.
4. Capture the Backend Application's public URL.
5. Configure the **Frontend** Application's environment:
   `NEXT_PUBLIC_BACKEND_API_URL=<backend URL from step 4>`.
6. Deploy the Frontend Application (Script: `frontend/app_cai_frontend.py`).
7. Capture the Frontend Application's public URL.
8. Update the Backend Application's `CORS_ORIGINS` to the Frontend URL from
   step 7.
9. Restart the Backend Application so the new CORS origin takes effect.
10. Run end-to-end validation (§8).

## 8. Health validation

Backend, directly:
```bash
curl -s $BACKEND_URL/api/health
curl -s $BACKEND_URL/api/deployment/readiness
```

`/api/deployment/readiness` aggregates `backend_api`, `semantic_layer`,
`data_backend`, `market_api`, `llm_provider` as `healthy` / `degraded` /
`unavailable`, with an overall rollup. It never returns secrets, tokens, or
raw error payloads.

End-to-end smoke test, targeting the Backend Application directly (this is
what actually proves Frontend-configured-backend connectivity and
Backend→Qwen connectivity, since the Frontend has no server-side API
surface of its own):
```bash
.venv/bin/python scripts/smoke_cai_app.py --backend-url $BACKEND_URL
```
This exercises: application health, readiness, dashboard data, and five
representative governed questions (historical, forecast, weather,
market/competitor, external market). It fails loudly if any response
contains a raw stack trace, 500 error, or non-JSON payload.

Also load the Frontend URL in a browser and confirm: Dashboard renders,
filters work, floating Ask AI responds, Ask AI page works, AI Monitoring
loads, Settings shows only the simplified business-facing sections.

## 9. Troubleshooting

Grouped by which service is at fault — logs are prefixed `[frontend]`,
`[backend]`, or `[market-api]` to make this easy to tell apart.

**Frontend problem**
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `app_cai_frontend.py` exits with `NEXT_PUBLIC_BACKEND_API_URL is required` | Env var not set before build | Set it to the deployed Backend URL, then re-run |
| Page loads but every API call fails in the browser console with a CORS error | Backend's `CORS_ORIGINS` doesn't include the Frontend's actual URL | Update `CORS_ORIGINS` on the Backend Application and restart it (§7 step 8–9) |
| Frontend shows stale backend behavior after changing `NEXT_PUBLIC_BACKEND_API_URL` | The value is baked in at build time, not read at runtime | Rebuild: re-run `app_cai_frontend.py` without `BUILD_SKIP=1` |

**Backend problem**
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `app_cai_backend.py` exits with `DuckDB runtime file not found` | Demo data never generated | `python3 scripts/generate_sample_data.py` |
| `/api/deployment/readiness` shows `data_backend: unavailable`/`degraded` | DuckDB file missing/corrupt, or `DATA_BACKEND` misconfigured | Check the Backend Application's logs |

**Qwen connectivity problem**
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `app_cai_backend.py` exits with `QWEN_BASE_URL is required` | `LLM_MODE=remote` without Qwen env vars set | Set `QWEN_BASE_URL`/`QWEN_MODEL` via CAI secrets, or use `LLM_MODE=mock` for a non-LLM smoke check |
| `/api/deployment/readiness` shows `llm_provider: degraded` | Qwen endpoint configured but connectivity not confirmed (network egress, Qwen app down) | Confirm the Qwen Application is running and reachable from the Backend Application's network |
| Chat responses fail once `LLM_MODE=remote` | Env var name mismatch — the app reads `QWEN_BASE_URL`/`QWEN_MODEL`/`QWEN_API_TOKEN`, not `LLM_BASE_URL`/`LLM_MODEL` | Confirm the Backend's env uses the `QWEN_*` names exactly as in `.env.example` |

**Market API problem**
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `/api/deployment/readiness` shows `market_api: unavailable` | Mock Market API process died inside the Backend Application, or `MARKET_API_BASE_URL` misconfigured | Check the Backend Application's logs for `[market-api]`-prefixed lines (CAI Application Logs console; `runtime/market-api.log` when using the legacy shell scripts locally) |

**Data backend problem**
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Dashboard loads but shows empty charts/KPIs | DuckDB file present but empty/stale | Re-run `python3 scripts/generate_sample_data.py` |
| Port already in use on restart | A previous run wasn't cleaned up | Both entrypoints clean up their child processes on shutdown/interrupt; check for stray manual `uvicorn`/`next start` processes |

## 10. Transition to live Trino/CDW (future step)

This milestone intentionally does not require Trino credentials, and does
not create any Trino schema. When ready to certify live Trino/CDW
(Milestone 5.6 / post-deployment):

1. On the **Backend Application only**, set `DATA_BACKEND=trino`.
2. Provide `TRINO_JDBC_URL` (or `TRINO_HOST`/`TRINO_PORT`/`TRINO_HTTP_SCHEME`),
   `TRINO_CATALOG`, `TRINO_SCHEMA`, and either `TRINO_USER`+`TRINO_PASSWORD`
   or `TRINO_ACCESS_TOKEN`, via CAI secrets — never in source.
3. Re-run the backend regression suite and the smoke test against the Trino
   path before promoting it as the default.
4. **The Frontend Application requires zero changes** — the data-backend
   abstraction is entirely server-side; only the Backend's `DATA_BACKEND`
   configuration changes.

## 11. Legacy single-application path (local testing only)

`scripts/run-cai-app.sh` still exists for quick local all-in-one testing:
one process group, one port, same-origin `/api/*` proxying via
`next.config.mjs`. It is **not** the deployment target — do not use it to
deploy to real Cloudera AI Applications. For that, use §6-§7 above.

```bash
bash scripts/run-cai-app.sh
.venv/bin/python scripts/smoke_cai_app.py --base-url http://127.0.0.1:3000
```
