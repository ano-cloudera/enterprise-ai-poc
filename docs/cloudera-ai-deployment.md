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
      | same-origin browser fetch("/api/...") — no cross-origin call, ever
      v
Next.js server (same process) — next.config.mjs rewrite
      |
      | server-to-server HTTPS (BACKEND_API_URL, not NEXT_PUBLIC_*)
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

**Important**: the browser never calls the Backend Application's URL
directly. CAI's gateway (Istio) was observed to reject cross-origin
requests between Application domains outright — with a bare
`Disallowed CORS origin` response from `istio-envoy` — even with the
Backend's own `CORS_ORIGINS` correctly set to the Frontend's URL and even
after enabling **Site Administration → Security → Feature Flags → Enable
cross-origin resource sharing**. That flag did not change the observed
behavior in this deployment (its effect and propagation are platform
infrastructure outside this application's control). Rather than depend on
that, the Frontend proxies `/api/*` **server-side** via
`next.config.mjs`'s `rewrites()`, using the plain server env var
`BACKEND_API_URL` (not `NEXT_PUBLIC_*`, so it's read at request time on
the Next.js server, never shipped to the browser). The browser only ever
sees one origin — the Frontend's own — so there is no cross-origin request
for any CORS policy to block, browser-side or gateway-side.
`CORS_ORIGINS` on the Backend is still set for defense-in-depth (direct
`curl`/API testing, or a future consumer that does need cross-origin
access) but is no longer on the browser's request path.

**Only two applications are created in this milestone**: Tempo Scan
Frontend and Tempo Scan Backend. The Qwen application already exists — do
not redeploy or modify it. There is no fourth application for the Mock
Market API; it runs as an internal process inside the Backend Application.

**Optional fourth application — Tempo Scan LiteLLM Router**: when
`LITELLM_BASE_URL` is set on the Backend Application, the Backend calls
this router (`litellm/config.yaml`, entrypoint
`litellm/app_cai_litellm.py`) instead of calling the Qwen Application
directly. It exists so which model(s) actually serve a request — Qwen
today, an additional provider or the planned Cloudera Agent Studio
workflow later — is a config change in `litellm/config.yaml`, not a
backend code change. Leaving `LITELLM_BASE_URL` unset (the default) skips
this application entirely and the Backend keeps calling Qwen directly, as
in §1's diagram above — deploy this only if/when you actually want the
routing layer. See §3.3.

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
- Python 3.10 available in the CAI runtime image (e.g. PBJ Workbench or
  JupyterLab Python 3.10 standard). Node.js is **not** required on the
  image — `frontend/app_cai_frontend.py` downloads a portable Node.js 20
  LTS build automatically on first start if `npm`/`node` aren't already on
  `PATH` (CAI's Python-only runtime images have neither).
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
| `CORS_ORIGINS` | no | `https://tempo-frontend.cai.example` | no | Defense-in-depth only — the deployed Frontend proxies API calls server-side and never triggers browser CORS (§1). Useful for direct/cross-origin API consumers besides the Frontend. Comma-separated, no wildcard in production |
| `DATA_BACKEND` | no (default `duckdb`) | `duckdb` | no | `duckdb` for this milestone; `trino` later (§10) |
| `DUCKDB_PATH` | no | `runtime/tempo_scan.duckdb` | no | Relative to repo root |
| `LLM_MODE` | no (default `mock`) | `remote` | no | `mock` = offline deterministic; `remote` = calls Qwen |
| `QWEN_BASE_URL` | yes if `LLM_MODE=remote` | `https://qwen-model.ml-....cloudera.site/v1` | no (URL only) | Existing Qwen Application's public URL |
| `QWEN_MODEL` | yes if `LLM_MODE=remote` | `Qwen3.8-27B-AWQ` | no | Model name served by Qwen Application |
| `QWEN_API_TOKEN` | if Qwen requires auth | — | **yes** | Set via CAI secrets only |
| `MARKET_API_INTERNAL_PORT` | no (default `18100`) | `18100` | no | Internal port for the Mock Market API child process, set automatically as `MARKET_API_BASE_URL`. Only override if it collides with `CDSW_APP_PORT` |
| `SERPER_API_KEY` | no | — | **yes** | Only used by manual refresh scripts, not at runtime |
| `SERPER_ENABLED` | no (default `false`) | `false` | no | Keep `false` for normal startup |

### 3.2 Frontend Application environment variables

`NEXT_PUBLIC_APP_NAME`/`NEXT_PUBLIC_CUSTOMER_NAME` are inlined into the
browser bundle at build time — do not put secrets in any `NEXT_PUBLIC_*`
variable. `NEXT_PUBLIC_BACKEND_API_URL` is the one exception that never
reaches the browser: `app_cai_frontend.py` reads it and re-exports it as
the plain server env var `BACKEND_API_URL`, which only
`next.config.mjs`'s server-side rewrite uses (§1) — the `NEXT_PUBLIC_`
prefix here is a historical naming leftover, not a sign it's client-side.

| Variable | Required | Example | Secret? | Description |
| --- | --- | --- | --- | --- |
| `NEXT_PUBLIC_BACKEND_API_URL` | **yes** | `https://tempo-backend.cai.example` | no | Deployed Backend Application's public URL. Server-side only — see above. No trailing slash needed |
| `NEXT_PUBLIC_APP_NAME` | no | `Commercial Intelligence` | no | Cosmetic, client-side |
| `NEXT_PUBLIC_CUSTOMER_NAME` | no | `Tempo Scan` | no | Cosmetic, client-side |

Never set `QWEN_API_TOKEN`, `SERPER_API_KEY`, `TRINO_PASSWORD`,
`TRINO_ACCESS_TOKEN`, or any database credential on the Frontend
Application. The frontend never talks to Qwen directly — only the Backend
does.

**Important**: because `NEXT_PUBLIC_*` values are baked in at build time,
changing `NEXT_PUBLIC_BACKEND_API_URL` requires rebuilding the frontend
(`frontend/app_cai_frontend.py` rebuilds by default every start — see §6).

### 3.3 LiteLLM Router Application environment variables (optional)

Only needed if you deploy the fourth application described above. Skip
this section entirely if `LITELLM_BASE_URL` stays unset on the Backend.

| Variable | Required | Example | Secret? | Description |
| --- | --- | --- | --- | --- |
| `QWEN_BASE_URL` | **yes** | `https://qwen-model.ml-....cloudera.site/v1` | no (URL only) | Same existing Qwen Application URL as the Backend's §3.1 — this Application's own `config.yaml` reads it directly, independent of the Backend's copy |
| `QWEN_MODEL` | **yes** | `Qwen3.8-27B-AWQ` | no | Same value as the Backend's §3.1 |
| `QWEN_API_TOKEN` | if Qwen requires auth | — | **yes** | Set via CAI secrets only |
| `QWEN_REQUEST_TIMEOUT_SECONDS` | no (default `60`) | `60` | no | Forwarded into `config.yaml`'s per-model timeout |
| `AGENT_STUDIO_BASE_URL` | no | — | no (URL only) | Leave unset until the Cloudera Agent Studio workflow is provisioned — the `agent-studio-workflow` model group in `config.yaml` is a placeholder until then and any request to it fails over to `commercial-intelligence` |
| `AGENT_STUDIO_API_TOKEN` | if Agent Studio requires auth | — | **yes** | Set via CAI secrets only, once provisioned |

Then, on the **Backend** Application, set:

| Variable | Required | Example | Secret? | Description |
| --- | --- | --- | --- | --- |
| `LITELLM_BASE_URL` | to enable routing | `https://tempo-litellm.cai.example` | no | This Application's own public URL. Leave unset to keep the Backend calling Qwen directly |
| `LITELLM_API_KEY` | no | — | **yes** | Only if you add proxy authentication to `config.yaml`; unset by default |
| `LITELLM_MODEL_GROUP` | no (default `commercial-intelligence`) | `commercial-intelligence` | no | Must match a `model_name` in `litellm/config.yaml` |
| `LITELLM_USE_AGENT_STUDIO` | no (default `false`) | `false` | no | Leave `false` until Agent Studio is provisioned and `AGENT_STUDIO_BASE_URL` is set above. When `true` before that, requests still succeed (LiteLLM falls back to `commercial-intelligence`) and the user sees a caveat explaining the fallback — never a silent swap |

The Backend's own `QWEN_*` variables (§3.1) become unused once
`LITELLM_BASE_URL` is set — they only matter for the direct-to-Qwen path.

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
an internal child process on `127.0.0.1:18100` by default (log-prefixed
`[market-api]`; override with `MARKET_API_INTERNAL_PORT` only if it happens
to collide with the `CDSW_APP_PORT` CAI assigns this Application) and waits
for its `/health`, then starts FastAPI bound to `127.0.0.1:$CDSW_APP_PORT`
(log-prefixed `[backend]`) and waits for `/api/health`. Does **not** start
the frontend. Fails loudly if any step
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
   Application above. `CORS_ORIGINS` can be left at its default —
   it's defense-in-depth only, not on the browser's request path (see §1).
3. Validate the Backend directly: `curl $BACKEND_URL/api/health` and
   `curl $BACKEND_URL/api/deployment/readiness`.
4. Capture the Backend Application's public URL.
5. Configure the **Frontend** Application's environment:
   `NEXT_PUBLIC_BACKEND_API_URL=<backend URL from step 4>` (this becomes
   `BACKEND_API_URL` for the server-side proxy; the browser never sees it —
   see §1).
6. Deploy the Frontend Application (Script: `frontend/app_cai_frontend.py`).
7. Capture the Frontend Application's public URL and open it — the
   browser only ever calls this URL's own `/api/*`, proxied server-side to
   the Backend.
8. Run end-to-end validation (§8).

Optional hardening: once the Frontend URL is known, set the Backend's
`CORS_ORIGINS` to it anyway, for any future direct/cross-origin consumer
of the Backend API. This is not required for the deployed Frontend to work.

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
| Page loads but every API call 404s or times out | `next.config.mjs`'s rewrite target is wrong — `NEXT_PUBLIC_BACKEND_API_URL` is malformed or the Backend Application is down | Check the Frontend Application Logs for the printed Backend URL at startup; fix the env var and restart |
| Browser console shows a CORS error | Should not happen — the browser only ever calls this app's own origin (§1), proxied server-side to the Backend | Something is bypassing the `/api/*` proxy and calling the Backend URL directly from client code; check for a stray fetch to the Backend's own domain outside `frontend/src/lib/api.ts` |
| Frontend shows stale backend behavior after changing `NEXT_PUBLIC_BACKEND_API_URL` | `next.config.mjs` reads it fresh from `BACKEND_API_URL` (set by `app_cai_frontend.py`) on every process start — a rebuild is not required | Restart the Frontend Application (no rebuild needed for this specific change) |
| `FileNotFoundError: ... 'npm'` | Runtime image is Python-only (PBJ Workbench / JupyterLab), no Node.js pre-installed | Should self-heal on its own — `app_cai_frontend.py` downloads a portable Node.js 20 build automatically. If this error still appears, confirm you're on the latest commit (`git pull`) and that the Application's egress can reach `nodejs.org` |

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
3. Load governed tables into Trino/Iceberg using the **dedicated loader
   identity** (`TRINO_LOADER_*` variables — never reuse the application's
   `TRINO_*` credential):
   - `python scripts/bootstrap_trino_demo.py --dry-run` then without
     `--dry-run` — loads `commercial_sales_daily` and
     `commercial_inventory_daily`, and runs the hero-story validation
     (Jawa Barat decline) against what Trino actually returns.
   - `python scripts/bootstrap_trino_extended.py --dry-run` then without
     `--dry-run` — loads `commercial_product_master`,
     `commercial_weather_monthly`, `commercial_market_monthly`, and
     `commercial_market_digital_snapshot` from the local DuckDB runtime.
     Skips any table with no rows yet in the local runtime rather than
     failing (e.g. run `scripts/fetch_weather_history.py` /
     `scripts/generate_market_data.py` / `scripts/fetch_market_snapshot.py`
     first if a table is missing).
   - `commercial_sales_forecast` is loaded separately through
     `app.forecasting.persistence.TrinoForecastWriter`, which replaces rows
     scoped to one `model_version` rather than the whole table — this stays
     a training-job concern, not part of either bootstrap script above.
   All tables are created `WITH (format = 'ICEBERG')`.
4. Re-run the backend regression suite and the smoke test against the Trino
   path before promoting it as the default.
5. **The Frontend Application requires zero changes** — the data-backend
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
