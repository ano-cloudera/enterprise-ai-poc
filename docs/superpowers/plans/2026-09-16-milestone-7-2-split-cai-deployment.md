# Milestone 7.2: Split Cloudera AI Deployment (Frontend + Backend + existing Qwen)

Date: 2026-09-16
Status: Complete (local two-port split validation). LIVE_SPLIT_CAI_VALIDATION=PENDING.

## Goal

Replace the single-CAI-Application packaging from Milestone 7
(`scripts/run-cai-app.sh`) with a 3-application architecture:

1. **Tempo Scan Frontend** (new CAI Application) — Next.js production build.
2. **Tempo Scan Backend** (new CAI Application) — FastAPI + LangGraph +
   semantic layer + Mock Market API served internally + DuckDB.
3. **Existing Qwen/vLLM** (already deployed, untouched) — the code at
   `testing/vllm_testing/vllm/` (`proxy.py` fronting vLLM on
   `VLLM_INTERNAL_PORT`, default 9000) is confirmed by the user to already
   be the running CAI Application for Qwen. Not redeployed, not modified.

Only 2 new CAI Applications are created in this milestone. No 4th
application for the Mock Market API — it stays internal to the Backend
process, same as Milestone 7.

## Repository inspection findings

- `frontend/src/lib/api.ts` — **single choke point** for all frontend→backend
  calls: `request()` always does `fetch(`/api${path}`, ...)`, a same-origin
  relative path. This is the only place that needs to become
  configurable via `NEXT_PUBLIC_BACKEND_API_URL`. No other component/file
  calls `fetch` or references `/api` directly (confirmed via grep).
- `frontend/next.config.mjs` — the `/api/:path*` rewrite to
  `BACKEND_API_URL` (server-side, Milestone 7's same-origin proxy) becomes
  unnecessary once the frontend calls the backend's public HTTPS URL
  directly from the browser. Left in place (harmless, unused in split mode)
  rather than deleted, since deleting it would remove Milestone 7's
  same-origin/local-dev path for no benefit — it simply won't be hit when
  `NEXT_PUBLIC_BACKEND_API_URL` is set to a cross-origin backend URL.
- `backend/app/core/config.py` already has `cors_origins` /
  `cors_origin_list`, wired into `CORSMiddleware` in `backend/app/main.py`.
  This already **is** the `CORS_ALLOWED_ORIGINS` mechanism the spec asks
  for — reusing the existing `CORS_ORIGINS` env var name rather than
  introducing a duplicate `CORS_ALLOWED_ORIGINS` name that would silently
  do nothing (Settings only binds fields it declares).
- `backend/app/api/routes/health.py` already has `/api/health` and (from
  Milestone 7) `/api/deployment/readiness` — reused as-is, no changes
  needed for the split; both already avoid leaking secrets.
- `backend/app/mock_market_api/main.py` stays served internally
  (`127.0.0.1:8100`) from inside the Backend Application process, started
  by the new `scripts/run-cai-backend.sh` — matches "do not create a
  separate Mock Market API CAI Application."
- `testing/vllm_testing/vllm/proxy.py` — confirmed existing, separate,
  already-deployed Qwen CAI Application entrypoint. Not touched.
- Milestone 7's `scripts/run-cai-app.sh` combined all three local processes
  behind one public port — this becomes the **legacy single-app path**,
  kept for local all-in-one dev/testing, clearly marked as legacy and not
  the CAI split-deployment path.

## Non-goals (explicit constraints from the instructions)

- No new Qwen CAI Application; no vLLM/model/GPU config changes.
- No 4th (Market API) CAI Application.
- No UI redesign, no forecasting/model changes.
- No Trino schema creation or live Trino persistence yet (next milestone).
- No wildcard CORS in production.
- No secrets in `NEXT_PUBLIC_*` frontend env vars.

## Plan of changes

1. `frontend/src/lib/api.ts` — introduce a single `API_BASE_URL` constant
   from `process.env.NEXT_PUBLIC_BACKEND_API_URL` (empty string fallback =
   same-origin, preserving Milestone 7 local behavior when unset), used by
   the existing `request()` helper. No other frontend file needs to change
   since this is the only fetch choke point.
2. `scripts/run-cai-frontend.sh` — new. Validates
   `NEXT_PUBLIC_BACKEND_API_URL` is set (fails clearly if not), builds if
   needed, binds `next start` to `0.0.0.0:$CDSW_READONLY_PORT`. Logs
   prefixed `[frontend]`.
3. `scripts/run-cai-backend.sh` — new. Validates backend env
   (`DATA_BACKEND`, DuckDB file presence, `LLM_MODE=remote` →
   `QWEN_BASE_URL`/`QWEN_MODEL` required), starts the Mock Market API
   internally on `127.0.0.1:8100` (logs prefixed `[market-api]`), then
   starts FastAPI bound to `0.0.0.0:$CDSW_READONLY_PORT` (logs prefixed
   `[backend]`) so it's reachable from the separate Frontend Application.
   Cleans up the internal market API process on shutdown.
4. `scripts/run-cai-app.sh` — keep as-is functionally, add a header comment
   marking it **legacy / single-app local validation**, and point to the
   new split scripts. Not deleted (still useful for quick local all-in-one
   testing).
5. `.env.example` — add a `Frontend (public-safe only)` section
   documenting `NEXT_PUBLIC_BACKEND_API_URL` (and optional
   `NEXT_PUBLIC_APP_NAME`/`NEXT_PUBLIC_CUSTOMER_NAME`), and confirm/document
   `CORS_ORIGINS` as the mechanism for restricting the backend to the
   deployed frontend's origin.
6. `docs/cloudera-ai-deployment.md` — rewritten to document the 3-application
   architecture, two variable tables (frontend/backend), deployment order
   (Qwen already running → Backend → capture URL → configure/deploy
   Frontend → capture URL → set backend CORS → restart backend → validate),
   sizing baselines, troubleshooting per service boundary, and the Trino
   next-step note (unchanged intent from Milestone 7, re-scoped to split
   architecture).
7. `scripts/smoke_cai_app.py` — extend to accept a separate `--backend-url`
   so it can validate a split deployment (frontend URL for page load-style
   checks is out of scope for a Python script; the smoke test targets the
   backend's public URL directly, which is what actually proves FE↔BE↔Qwen
   connectivity end-to-end). Keep `--base-url` working for the legacy
   single-app path.
8. Backend/frontend regression: `pytest backend/tests`, `npm test`,
   `npm run build`, `scripts/validate_bundle.py`.
9. Local split validation: run `run-cai-backend.sh` on one port and
   `run-cai-frontend.sh` on another (simulating two separate CAI
   Applications, each with its own `CDSW_READONLY_PORT`), with
   `NEXT_PUBLIC_BACKEND_API_URL` pointing frontend at backend's port, and
   confirm cross-origin requests succeed only from the configured CORS
   origin.

## Validation

- `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests`
- `npm test` / `npm run build` (frontend)
- `.venv/bin/python scripts/validate_bundle.py`
- Local two-port split run + `scripts/smoke_cai_app.py --backend-url ...`
- `LIVE_SPLIT_CAI_VALIDATION=PENDING` unless this session is confirmed to be
  running inside real Cloudera AI Application infrastructure.
