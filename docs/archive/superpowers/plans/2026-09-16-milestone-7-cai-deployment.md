# Milestone 7: Cloudera AI Deployment Readiness

Date: 2026-09-16
Status: Complete (local CAI-compatible validation). LIVE_CAI_VALIDATION=PENDING.

## Goal

Deploy the existing Tempo Scan Commercial Intelligence Assistant (frontend +
FastAPI backend + local DuckDB demo data + Mock External Market API + remote
Qwen/vLLM) as a single Cloudera AI Application, reachable through one public
URL, without live Trino credentials.

This is deployment packaging only. No new analytics, no UI redesign, no
model-serving refactor.

## Repository inspection findings (baseline, before changes)

- `frontend/next.config.mjs` already rewrites `/api/:path*` to
  `BACKEND_API_URL` (default `http://127.0.0.1:8000`) — same-origin proxy
  already exists, no new proxy code needed.
- `frontend/package.json` `start` script runs `next start -H 0.0.0.0` but is
  hardcoded to Next's default port 3000 — does **not** read
  `CDSW_READONLY_PORT` or `$PORT`. Needs a `-p` flag driven by env var.
- `scripts/run-local.sh` / `run-api.sh` / `run-web.sh` / `run-market-api.sh`
  exist for local dev (uvicorn `--reload`, `npm run dev`) — not
  production-safe and not CAI-port-aware. A new `scripts/run-cai-app.sh` is
  needed rather than reusing these for the CAI path.
- `backend/app/api/routes/health.py` already returns a safe `/health` (data
  backend status + model backend status via `SecretStr`, no secrets
  leaked). Mock Market API already has `/health` returning row counts only.
  No monitoring/health route currently aggregates frontend + backend +
  market API + Qwen in one view — this is what CAI readiness needs.
- `backend/app/core/config.py` defines `llm_mode` (`mock`/`remote`),
  `qwen_base_url`, `qwen_model`, `qwen_api_token` (SecretStr),
  `market_api_base_url`, `data_backend` (`duckdb`/`trino`/`impala`),
  `duckdb_path` (relative, resolved from process CWD).
- **Finding**: the repo's local `.env` (gitignored, not part of this
  milestone's diff) sets `LLM_BASE_URL` / `LLM_MODEL` /
  `LLM_ENABLE_THINKING`, which do **not** match the `Settings` field names
  (`QWEN_BASE_URL` / `QWEN_MODEL` / `QWEN_DISABLE_THINKING`) and are
  silently ignored by pydantic-settings. Harmless today because
  `LLM_MODE=mock`, but will silently break remote Qwen connectivity if
  switched to `remote` without fixing the variable names. Documented in
  `.env.example` and the deployment doc; not auto-corrected in the user's
  local `.env` since that file is out of this diff's scope.
- `runtime/tempo_scan.duckdb` and `backend/runtime/tempo_scan.duckdb` both
  exist already (committed-adjacent, gitignored). The app resolves
  `duckdb_path` relative to CWD, so the working directory at process start
  determines which one is used. The CAI startup script must `cd` to repo
  root before starting the backend so the intended `runtime/tempo_scan.duckdb`
  is used deterministically.
- `scripts/validate_bundle.py` already checks required files exist and the
  Jawa Barat hero decline story holds — reused as-is as part of packaging
  validation, not modified.
- No `scripts/smoke_cai_app.py` exists yet — created new.

## Non-goals (explicitly out of scope per instructions)

- No new AI features, no UI redesign, no forecasting/model changes.
- No Kubernetes/Docker Compose/PM2/Supervisor.
- No live Trino/CDW certification (stays Milestone 5.6 / post-deployment).
- No live Serper.dev/Open-Meteo calls during startup.

## Plan of changes

1. `frontend/package.json` — production `start` script binds to
   `0.0.0.0:${PORT:-${CDSW_READONLY_PORT:-3000}}` instead of the Next.js
   default port.
2. `backend/app/api/routes/health.py` (or a new aggregate route) — add a
   deployment-readiness view combining frontend reachability expectation,
   backend API, semantic layer load, DuckDB backend, Mock Market API
   reachability, and Qwen configuration presence — healthy/degraded/
   unavailable, no secrets.
3. `scripts/run-cai-app.sh` — new single entrypoint: validates required env
   vars, starts Mock Market API (127.0.0.1:8100), starts FastAPI backend
   (127.0.0.1:8000), builds+starts Next.js frontend on
   `CDSW_READONLY_PORT`/`PORT`, traps shutdown to kill children, fails
   loudly if any service does not come up.
4. `.env.example` — reorganize into Application / LLM / Data Backend /
   Market API / Optional External Refresh sections, add `APP_ENV=production`
   example and confirm `QWEN_*` naming matches `Settings` fields exactly (fix
   the drift found above at the documentation level).
5. `docs/cloudera-ai-deployment.md` — new deployment guide (prereqs, env
   vars, install, build, startup command, expected URL behavior, health
   validation, troubleshooting, Trino transition note).
6. `scripts/smoke_cai_app.py` — new end-to-end smoke test hitting the
   deployed app's same-origin `/api/*` routes for health, dashboard, and the
   five representative questions from the milestone spec.
7. Backend/frontend regression run: `pytest backend/tests`, `npm test`,
   `npm run build`, `scripts/validate_bundle.py`.

## Validation

- `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests`
- `npm test` / `npm run build` (frontend)
- `.venv/bin/python scripts/validate_bundle.py`
- `bash scripts/run-cai-app.sh` started locally (CAI-compatible path, not
  actual Cloudera AI infrastructure) + `scripts/smoke_cai_app.py` against it.
- `LIVE_CAI_VALIDATION=PENDING` unless this session is confirmed to be
  running inside a real Cloudera AI Application environment.
