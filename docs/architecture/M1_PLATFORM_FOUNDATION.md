# M1 — Platform Foundation

**Status:** Implemented and **M1_VERIFIED** (13 Oct 2026) — see validation gate below

## Goals

Reusable accelerator metadata and persistence without breaking Ask Data (`/chat`, `/chat/stream`, `AskDataResponse`).

## Store abstraction

| Interface | SQLite | PostgreSQL |
|-----------|--------|------------|
| `ConversationStoreProtocol` | `SQLiteConversationStore` (legacy `messages` table) | `PostgresConversationStore` (`conversations` / `messages`) |
| `UsageStoreProtocol` | `SQLiteUsageStore` (`llm_usage_events`) | `PostgresUsageStore` (`usage_events`) |

Configuration: `STATE_STORE=sqlite|postgres`, `DATABASE_URL` (or `POSTGRES_URL`).

Factory: `app/stores/factory.py` — Postgres errors **fall back to SQLite** so local/dev stays up.

## PostgreSQL entities (M1 only)

- `workspaces`, `projects`, `conversations`, `messages`, `usage_events`

Migrations: `backend-dev/alembic/` (`alembic upgrade head` with `DATABASE_URL` set).

Startup also runs `create_all` + idempotent seed when `STATE_STORE=postgres`.

## Default workspace / project

Seed creates:

- Workspace slug `default`
- Project slug `tempo_scan_impala` → OSSIE path `projects/tempo_scan_impala`

Ask Data resolves semantic root via `resolve_ossie_project_dir()` when Postgres is active; otherwise legacy `project_root / ossie_project_id`.

## Secret provider

`SecretProvider` + `EnvSecretProvider` in `app/secrets/provider.py` (env-first; no Vault in M1).

## API

Legacy unchanged: `/chat`, `/chat/stream`, `/models`, `/random-queries`, `/usage/*`, `/health`, `/health/ready`.

New (Postgres required): `/api/v1/workspaces`, `/api/v1/workspaces/default`, `/api/v1/projects`, `/api/v1/projects/default`.

## Frontend

`src/config/appConfig.ts` — `features.*` drives sidebar nav; disabled M2 areas are not linked.

Branding: `appName`, `appSubtitle`, `projectName`, logos, placeholders via `NEXT_PUBLIC_*`.

## M1 validation gate (13 Oct 2026)

| Check | Result |
|-------|--------|
| Alembic `upgrade head` (Docker Postgres 16, port 55432) | Pass |
| Default workspace/project seed | Pass |
| Postgres conversation + usage round-trip | Pass |
| Simulated restart (new store instances) | Pass |
| `STATE_STORE=postgres` app startup + `/api/v1/*` | Pass |
| `/chat/stream` SSE terminal `done` (HTTP smoke; FakeChatService) | Pass |
| `STATE_STORE=sqlite` + Postgres-unavailable fallback | Pass |
| Focused M1 pytest (`test_stores_factory`, resolver, history, usage) | 23 passed |
| Live full LangGraph Ask Data + LLM on Postgres | Not run (no LLM creds in smoke); persistence path validated via stores |

Smoke script: `backend-dev/scripts/m1_postgres_smoke.py` (set `DATABASE_URL` or use default local container).

Startup log (no secrets): `state_store configured=… conversation_adapter=… usage_adapter=… postgres_configured=…`

### Known non-M1 test failures (classified)

**Backend (9):** all **PRE_EXISTING** test double / resolver drift — see `PROJECT_STATE.md` gate notes.

**Frontend (5):** **ENVIRONMENTAL** (Node localStorage) + **PRE_EXISTING** (timeout 90s vs 180s default; starter click without model `selection`).

## Out of scope (M1)

Documents, RAG, Qdrant, connectors UI, prompts/skills UI, Redis/RQ, second chat engine.

## M2 readiness

Platform metadata, store swap, and project resolution are in place. M2 may add document/library entities and Qdrant after the validation gate in ADR-003.
