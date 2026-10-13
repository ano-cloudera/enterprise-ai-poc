# ADR-007: Accelerator Pilot Defaults

**Status:** Accepted  
**Date:** 2026-10-13

Product owner decisions closing M0 open questions. Binding for M1+ unless explicitly revised.

| Topic | Decision |
|-------|----------|
| **Workspace** | **Single default workspace** in pilot (multi-workspace schema allowed later) |
| **State DB** | `STATE_STORE=sqlite` (local dev); `STATE_STORE=postgres` (**recommended** CAI pilot). Postgres **optional** — app must work on SQLite if Postgres unavailable ([ADR-008](ADR-008-STATE-STORE-AND-REDIS.md)) |
| **UsageStore** | **SQLite + PostgreSQL parity** (same abstraction pattern as ConversationStore) |
| **SQLite schema** | **Compatibility only** — keep existing SQLite layouts; **no normalization project** on SQLite |
| **Qdrant (M2)** | **Default design:** shared collection + metadata filtering — **strategy not finalized** until M2 validation gate ([RAG_DESIGN.md](../backend/RAG_DESIGN.md)) |
| **Background jobs** | **BackgroundTasks** default; **RQ optional only** if Redis present on CAI — Redis **not required** ([ADR-008](ADR-008-STATE-STORE-AND-REDIS.md)) |
| **Structured data** | **Impala first**, **Trino second** (connector/registry priority) |
| **Frontend shell** | **Custom Next.js** (`frontend-dev`) — not CAI Studio embed as core product |
| **Neo4j** | **Out of core accelerator scope** (Tempo reference may keep optional flag; not platform dependency) |
| **backend-test/** | **Keep** as **isolated reference** (exploratory DuckDB agent; not governed accelerator path) |

## Consequences

- M1 seeds one default `workspace` (+ default `project`) in Postgres when enabled.
- Postgres may use normalized `conversation`/`message`; SQLite keeps current tables via ConversationStore adapters.
- M2 Qdrant implementation starts with one shared collection per deployment (or per workspace), not per-library collections.
- M4 connector registry implements Impala before Trino adapter.
