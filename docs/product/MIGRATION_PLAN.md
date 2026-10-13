# Migration Plan — Tempo PoC → Cloudera AI Accelerator

## Principle

**Genericize the platform; do not rewrite working Ask Data.**

Existing `/chat` and LangGraph OSSIE workflow remain the execution core. New domains (knowledge, connectors, prompts, skills) attach around it.

## Phase alignment

| Phase | Work | Ask Data impact |
|-------|------|-----------------|
| M0 | Docs + audit | None |
| M1 | Postgres (CAI pilot), **single default workspace**, ConversationStore + **UsageStore** (SQLite/Postgres parity), config | SQLite **legacy schema unchanged**; **legacy `/chat` unchanged** |
| M2 | RAG pipeline | New routes; optional router branch |
| M3 | Prompt/skill DB | Replace disk prompts gradually |
| M4 | Connector registry | Impala/DuckDB implement `Connector` port |
| M5 | Hybrid router | Extends `ChatService` routing |
| M6 | Packaging | Deploy scripts only |

## Backend migration (least disruptive)

**Today:** flat `app/` with `services/`, `graph/`, `semantic/`, `db/`, `api/`.

**Target (conceptual packages, not big-bang directory move):**

1. Introduce `app/domains/` or rename incrementally: `ask_data/`, `conversations/`, `models/`, `usage/` (extract from existing modules).
2. Add `knowledge/`, `connectors/`, `prompts/`, `skills/`, `orchestration/` as new packages when M2+ starts.
3. Keep `app/main.py` router registration stable; add `/api/v1/...` routes that **call existing services** (no duplicate chat engine).
4. Preserve `/chat`, `/chat/stream`, `/models`, `/usage/*` as primary contracts for current FE.

**Do not** split into microservices for pilot.

## Frontend migration

1. Extend `appConfig.ts` with `features: { askData, documents, connectors, prompts, skills, usage }`.
2. Expand sidebar from 3 items → capability-driven list (flags off = hidden).
3. Reuse `AskDataPage`, Analysis Workspace, Usage, Settings as core shell.
4. Add placeholder routes only when backend exists (M2+).

**Studio UI** (Document AI, Connectors, Prompts, Skills in CAI Studio screenshots) is **out of scope** for this repo until explicitly integrated; do not assume those screens are implemented here.

## Data migration

| Current | Target |
|---------|--------|
| SQLite conversation history | Postgres via **ConversationStore** (M1, **no forced cutover**) |
| SQLite LLM usage | Postgres via **UsageStore** when enabled (M1) |
| Disk `prompts/*.md` | Postgres `prompts` / `prompt_versions` (M3) |
| OSSIE YAML in `projects/` | Remain source for semantic layer; project row points to path |
| DuckDB local gold | Dev-only; production uses connector |

## Sync policy: `backend-dev` ↔ `backend/`

Until M1 completes in dev tree, **cherry-pick** proven Ask Data fixes to `backend/` for production demos. Avoid divergent routing logic.

## Rollback strategy

- Feature flags disable new routes and router branches.
- Legacy `/chat/stream` contract unchanged through M1–M2.
- SQLite paths remain fallback until Postgres cutover is verified.
