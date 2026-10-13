# Cloudera AI Accelerator — Project State

**Repo:** `enterprise-ai-poc`  
**Updated:** 13 Oct 2026 (PM)  
**Phase:** **M1_VERIFIED — M2 not started**

## Project Goal

Evolve `frontend-dev/` + `backend-dev/` into a **reusable Cloudera AI Accelerator** for PoC/Pilot on **Cloudera AI Application**.

**Reference use case:** Tempo Scan (`projects/tempo_scan_impala/`) — not the product name.

Legacy Tempo checkpoint: [docs/archive/PROJECT_STATE_TEMPO_LEGACY.md](docs/archive/PROJECT_STATE_TEMPO_LEGACY.md)

## Current Milestone

| Milestone | Status |
|-----------|--------|
| M0 Architecture + audit | ✅ Complete |
| M1 Platform foundation | ✅ **M1_VERIFIED** (Postgres smoke + triage — 13 Oct 2026) |
| M2 Document / RAG | ⏸ Not started |

## M1 deliverables (implemented)

| Area | Location |
|------|----------|
| Store protocols + SQLite/Postgres adapters | `backend-dev/app/stores/` |
| Factory + SQLite fallback | `app/stores/factory.py`, `STATE_STORE` |
| Postgres entities + Alembic | `app/db/platform_models.py`, `backend-dev/alembic/` |
| Default workspace/project seed | `app/projects/bootstrap.py` |
| OSSIE path resolution | `app/projects/resolver.py` → `ChatService` |
| SecretProvider | `app/secrets/provider.py` |
| Platform API | `/api/v1/workspaces`, `/api/v1/projects` |
| FE feature flags + branding | `frontend-dev/src/config/appConfig.ts`, `AppShell.tsx` |

Details: [docs/architecture/M1_PLATFORM_FOUNDATION.md](docs/architecture/M1_PLATFORM_FOUNDATION.md)

## Binding decisions

### Architecture (M0 revisions)

1. ConversationStore + UsageStore — SQLite + Postgres; no hard cutover ([ADR-006](docs/decisions/ADR-006-CONVERSATION-STORE.md))
2. Legacy API — `/chat`, `/chat/stream`, `/models`, `/usage/*`; `/api/v1` reuses existing services
3. `AskDataResponse` stable; `UnifiedAIResponse` target only (no FE migration in M1)
4. Prompts — `workspace_id`, optional `project_id`, explicit `scope`
5. Connectors — extensible `type` + registry
6. NFS — Postgres/Qdrant/documents; Impala/Trino external
7. Background jobs — **BackgroundTasks** default ([ADR-005](docs/decisions/ADR-005-BACKGROUND-JOBS.md))

### Pilot defaults ([ADR-007](docs/decisions/ADR-007-PILOT-DEFAULTS.md))

Single default workspace; UsageStore parity; SQLite schema compatibility-only; Impala before Trino; custom Next.js FE; Neo4j out of core scope; keep `backend-test/` as isolated reference.

### State store & Redis ([ADR-008](docs/decisions/ADR-008-STATE-STORE-AND-REDIS.md))

| Setting | Environment |
|---------|-------------|
| `STATE_STORE=sqlite` | Local development (default) |
| `STATE_STORE=postgres` | CAI pilot (**recommended** in templates) |

- PostgreSQL is **optional/configurable** — app **must remain functional on SQLite** when Postgres is unavailable.
- **Redis is NOT required.** RQ is **optional only** when Redis exists on CAI.

### Qdrant (M2 — design not finalized)

- **Default M2 design:** shared collection + metadata filtering.
- **M2 validation gate** before locking strategy: latency, recall, filter overhead, isolation correctness, expected chunk/document volume.
- **Fallback if gate fails:** collection-per-library or collection-per-workspace ([RAG_DESIGN.md](docs/backend/RAG_DESIGN.md)).

## Current Architecture (as-is)

| Layer | Implementation |
|-------|----------------|
| FE | Custom Next.js — Ask Data, Usage, Settings, Analysis Workspace |
| BE | FastAPI + LangGraph OSSIE Ask Data |
| Session / usage | `STATE_STORE=sqlite` (default) or Postgres when configured |
| RAG / Qdrant | Not deployed |

## Do Not Change (without plan)

- Ask Data LangGraph path and stable `/chat` contracts
- Analysis Workspace UX
- Avoid large refactors in `frontend/` / `backend/` mirrors

## M1 verification gate (13 Oct 2026)

**Decision: M1_VERIFIED** — Postgres smoke passed (Docker `m1-pg-smoke`, `alembic upgrade head`, bootstrap, persistence, restart, fallback). Script: `backend-dev/scripts/m1_postgres_smoke.py`.

**No confirmed M1 regression** in failed tests (all classified PRE_EXISTING or ENVIRONMENTAL).

### Backend failure triage (337 pass / 9 fail / 1 skip)

| Test | Classification | Root cause (evidence) |
|------|----------------|------------------------|
| `test_chat_api::test_chat_reports_impala_auth_failure_without_exposing_driver_details` | PRE_EXISTING | Mock `_turn(_request, _history)` missing `request_id=` kwarg; production calls `_understand_turn(..., request_id=request_id)` at `chat.py:506` |
| `test_semantic_context::test_promo_roi_proxy_clarification_answer_in_prose_resolves_revenue_uplift` | PRE_EXISTING | Resolver now returns `material_sell_in_value_ratio` vs expected `promo_material_revenue_uplift` — OSSIE/heuristic drift, not store/project code |
| `test_workflow::test_greeting_is_written_by_selected_llm_without_querying_impala` | PRE_EXISTING | `FakeContext.guidance_context(question)` lacks `session_last_metric=`; workflow passes kwarg at `workflow.py:246` |
| `test_workflow::test_capability_conversation_is_guided_by_selected_llm_without_sql` (×6 parametrized) | PRE_EXISTING | Same `FakeContext.guidance_context` signature drift |

### Frontend failure triage (33 pass / 5 fail)

| Test | Classification | Root cause (evidence) |
|------|----------------|------------------------|
| `chatSessions.test.ts` (3 tests) | ENVIRONMENTAL | Node 25+ / Vitest: `localStorage` undefined — `beforeEach(() => localStorage.clear())` throws |
| `AskDataPage::loads starter questions…` | PRE_EXISTING | `submit()` returns early when `!selection` (`AskDataPage.tsx:108`); test clicks starter before model bootstrap |
| `AskDataPage::times out … after 90 seconds` | PRE_EXISTING | Test advances 120s but `streamTimeoutMs` defaults to **180_000** ms (`AskDataPage.tsx:119`, `.env.example`) |

## Open items (deferred to M2)

- **Qdrant collection strategy finalization** — after M2 validation gate only
- Wire optional `DATABASE_URL` in CI for Postgres smoke
- Repair PRE_EXISTING backend test doubles (`FakeContext`, `_understand_turn` mock) in a dedicated hygiene PR (not M1 scope)

## Dev quick reference

| Stack | Command | UI | API |
|-------|---------|-----|-----|
| Pilot | `./scripts/run-dev-stack.sh` | :3001 | :8001 |
| Prod mirror | `make dev` | :3000 | :8000 |
| Local state | `STATE_STORE=sqlite` | — | default |
| DuckDB data | `DATA_BACKEND=duckdb` | — | sample gold |
| Postgres migrate | `cd backend-dev && DATABASE_URL=... alembic upgrade head` | — | — |

Docs: [docs/README.md](docs/README.md)
