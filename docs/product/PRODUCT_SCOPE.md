# Cloudera AI Accelerator — Product Scope

**Status:** Phase 0 / Phase 1 (architecture & audit)  
**Working name:** Cloudera AI Accelerator  
**Deployment target:** Cloudera AI Application (CAI)

## Purpose

Reusable **application shell + backend framework** to accelerate **PoC / Pilot** AI projects on Cloudera — without rebuilding Ask Data, workspace UX, and LLM plumbing for every customer.

**Reference use case (not product identity):** Tempo Scan Commercial Intelligence (`tempo_scan_impala` OSSIE project) in `backend-dev/projects/` validates the Ask Data path.

## In-scope capabilities (target product)

| # | Capability | Phase 1 state |
|---|------------|---------------|
| 1 | **Ask Data** | **Implemented** in `backend-dev` / `frontend-dev` (governed OSSIE + LangGraph + Impala/DuckDB) |
| 2 | **Document Intelligence / RAG** | **Not implemented** — architecture only |
| 3 | **Hybrid Ask Data + RAG** | **Not implemented** — architecture only |
| 4 | **Connectors** | **Partial** — Impala/DuckDB as data backends, not pluggable connector domain |
| 5 | **Prompt Management** | **Partial** — markdown files on disk (`backend-dev/prompts/`), no versioning API |
| 6 | **Skills** | **Not implemented** — CAI Studio screenshots are a **different product shell**, not this repo |
| 7 | **Model Provider Management** | **Implemented** — registry + `/models` + Settings UI |
| 8 | **Usage / Observability** | **Partial** — LLM token usage SQLite + Usage page; no traces/audit API |

## Pilot defaults (ADR-007)

- **Workspace:** single default workspace  
- **State DB:** `STATE_STORE=sqlite` (local) / `STATE_STORE=postgres` (CAI pilot, recommended); Postgres optional — SQLite fallback required  
- **Redis:** not required; RQ optional when Redis on CAI  
- **UsageStore:** SQLite + Postgres parity with ConversationStore  
- **Structured connectors:** Impala first, Trino second  
- **Frontend:** custom Next.js (`frontend-dev`)  
- **Neo4j:** out of core accelerator scope (optional Tempo reference only)  
- **`backend-test/`:** kept as isolated exploratory reference (port 8001 clash documented)  
- **Qdrant (M2):** shared collection + filters (default design; finalize after validation gate)  

## PoC / Pilot boundary

This accelerator optimizes for:

- Fast deployment on CAI
- Single-instance PostgreSQL + Qdrant on NFS (future)
- Modular monolith backend
- Good domain boundaries for later production hardening

It is **not** (yet):

- Multi-tenant SaaS with enterprise IAM
- Mission-critical HA by default
- Full replacement for Cloudera AI Studio (Document AI, Connectors UI in marketing screenshots)

## Primary trees for evolution

| Tree | Role |
|------|------|
| `frontend-dev/` | Target accelerator frontend |
| `backend-dev/` | Target accelerator backend |
| `frontend/` / `backend/` | Production mirror / reference — **avoid large refactors** until dev tree stabilizes |

## Related docs

- [ROADMAP.md](./ROADMAP.md) — milestones M0–M6  
- [../architecture/ARCHITECTURE_V1.md](../architecture/ARCHITECTURE_V1.md)  
- [../architecture/CODEBASE_AUDIT.md](../architecture/CODEBASE_AUDIT.md)
