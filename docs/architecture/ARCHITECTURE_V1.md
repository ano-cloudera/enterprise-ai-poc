# Architecture V1 — Cloudera AI Accelerator

## System context

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  Cloudera AI Application (CAI)                                           │
│  ┌──────────────┐      /api proxy      ┌─────────────────────────────┐ │
│  │ Next.js FE   │ ◄──────────────────► │ FastAPI BE (modular monolith)│ │
│  │ frontend-dev │   /chat,/chat/stream │ backend-dev                  │ │
│  └──────────────┘                      └──────────────┬───────────────┘ │
└─────────────────────────────────────────────────────────┼──────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────┐
                        │         NFS volume (pilot)    │                       │
                        │  ┌────────────────────────────┼─────────────────────┐ │
                        │  │ PostgreSQL data dir (M1+)  │ Qdrant storage (M2+)│ │
                        │  │ documents/ parsed/ exports/│                     │ │
                        │  └────────────────────────────┴─────────────────────┘ │
                        └───────────────────────────────────────────────────────┘
                                                        │
                        External (customer cluster)     │
                        ┌───────────────────────────────▼───────────────────────┐
                        │  Impala / Trino — live structured data (NOT on NFS)   │
                        └───────────────────────────────────────────────────────┘
```

**Persistence rule:** NFS backs **PostgreSQL files**, **Qdrant persistence**, and **document artifacts**. Impala/Trino are **external** query engines reached over the network; connector credentials via SecretProvider.

## Architectural style

- **Modular monolith** (FastAPI + LangGraph in-process)
- **Optional workers** for parse/embed/sync (M2+) — not microservices initially
- **Domain-oriented** backend modules (not page-oriented services)

## Logical domains

| Domain | Responsibility |
|--------|----------------|
| `workspace` | Tenant boundary; **pilot: single default workspace** (ADR-007) |
| `project` | OSSIE/semantic config, prompts, skills, connector bindings |
| `conversation` / `message` | Multi-turn state |
| `model` | Provider registry configuration |
| `usage` | Token/cost telemetry |
| `knowledge` / `document` / `document_chunk` / `library` | RAG corpus |
| `connector` / `connector_sync` | External systems |
| `prompt` / `prompt_version` | Versioned instructions |
| `skill` / `skill_version` | Reusable agent capabilities |
| `tool` | Callable capabilities bound to skills |
| `audit` | Security-relevant events |

## Current implementation map (backend-dev)

| Domain | Today |
|--------|--------|
| conversation/message | `app/stores/*` — SQLite legacy + Postgres normalized (M1 ✅) |
| model | `llm/registry.py`, `api/models.py` |
| usage | `services/usage_store.py`, `api/usage.py` |
| ask_data | `services/chat.py`, `graph/workflow.py`, `semantic/*` |
| connector | **Ad hoc:** `db/impala_backend.py`, `db/duckdb_governed_backend.py` |
| knowledge/RAG | **Absent** |
| prompt | **Files:** `prompts/*.md` |
| skill | **Absent** |
| audit | **Absent** |

## Target AI routing (not implemented)

```text
User Question
      │
      v
Intent / Skill Router
      │
      ├── ask_data ──► OSSIE/LangGraph ──► SQL validate ──► connector
      ├── rag ─────► retrieve ──► rerank ──► LLM + citations
      ├── hybrid ──► parallel/sequential sub-routes ──► merge
      ├── general ─► conversational path
      └── clarification
      │
      v
Analysis Layer (shared analyst prompts, chart spec)
      │
      v
Unified Response (route-agnostic JSON + SSE)
```

Route types: `ask_data` | `rag` | `hybrid` | `general` | `clarification`.

## Ask Data flow (preserve)

Aligned with existing LangGraph in `app/graph/workflow.py`:

1. Understand turn (`conversational.py`)
2. Contextualize / follow-up (`question_contextualize.py`, `follow_up.py`)
3. Resolve metric/plan (`SemanticContextService`)
4. Generate & validate SQL (`sql/validator.py`, SQLGlot)
5. Execute (`ImpalaBackend` | `DuckDBGovernedBackend`)
6. Analyze + optional judge loop
7. Return `AskDataResponse` + optional SSE progress

## Conversation / session persistence (M1)

All chat history goes through a **ConversationStore** (or equivalent **Store** abstraction):

- **M1:** keep **SQLite** implementation (current `ConversationStore` behavior).
- **M1:** add **PostgreSQL** implementation behind the same interface.
- **Config:** `STATE_STORE=sqlite` (local dev) | `STATE_STORE=postgres` (CAI pilot recommended). Postgres **optional** — app must work on SQLite when Postgres unavailable ([ADR-008](../decisions/ADR-008-STATE-STORE-AND-REDIS.md)).
- **UsageStore** uses the same `STATE_STORE` selection with SQLite/Postgres parity.
- **No hard cutover:** optional import when enabling Postgres.

`ChatService` depends on the store interface only — not on a specific driver.

## API layering (M1)

- **Stable (unchanged):** `POST /chat`, `POST /chat/stream`, `GET /models`, `/usage/*`.
- **`/api/v1/*`:** new resource-oriented routes that **delegate to existing services** (`ChatService`, `ProviderRegistry`, `UsageStore`, etc.).
- **Do not** fork a second chat engine or duplicate LangGraph wiring for v1 routes.

## Response contracts

- **`AskDataResponse`** remains the **stable** contract for legacy routes and `frontend-dev` through M1+.
- **`UnifiedAIResponse`** is the **target** superset for future multi-route (RAG/hybrid) clients; optional mapping layer may emit it without breaking existing FE.

## Frontend architecture (frontend-dev)

- **Capability-driven shell** (`AppShell`) — today hardcoded 3 nav items; target `features.*` config
- **Reusable chat** + **Analysis Workspace** split pane
- **Proxy API** via Next rewrites to `BACKEND_API_URL`
- **Custom Next.js shell** is the accelerator FE (ADR-007) — not CAI Studio as core UI
- **No** embedded CAI Studio modules in this tree

## Technology choices

| Concern | Choice |
|---------|--------|
| FE | Next.js 15, React 19, Tailwind, Redux (model selection only) |
| BE | FastAPI, LangGraph, Pydantic v2 |
| Structured SQL | SQLGlot (Hive dialect → DuckDB dev) |
| Semantic layer | OSSIE YAML per `projects/<project_id>/` |
| Metadata DB (target) | PostgreSQL |
| Vectors (target) | Qdrant, bge-m3, bge-reranker-v2-m3 |
| Documents (target) | NFS + Docling parser interface |
| LLM | Qwen, Gemini, OpenAI-compatible via `ProviderRegistry` |

## M2 background work (accelerator mode)

- **Default:** FastAPI **BackgroundTasks** for parse / embed / reindex in pilot.
- **Optional:** **RQ** when Redis is available or workloads need durability/retries.

See [ADR-005](../decisions/ADR-005-BACKGROUND-JOBS.md) and [RAG_DESIGN.md](../backend/RAG_DESIGN.md).

## Extension paths (document only)

- PostgreSQL → external HA
- Qdrant → dedicated cluster
- NFS → S3/Ozone

See ADRs in `docs/decisions/`.
