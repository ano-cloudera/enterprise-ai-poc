# Codebase Audit — frontend-dev & backend-dev

**Date:** Phase 0/1 (Oct 2026)  
**Scope:** Accelerator evolution trees only.

## Summary

| Area | Maturity |
|------|----------|
| Ask Data (governed) | **Production-grade PoC** — LangGraph, OSSIE, SSE, tests |
| Analysis Workspace FE | **Strong** — reusable with env branding |
| Model providers | **Good** — registry abstraction |
| Usage metering | **Good** — SQLite + UI |
| RAG / Documents | **Missing** |
| Connectors domain | **Missing** (backends exist) |
| Prompts / Skills product | **Missing** (disk prompts only) |
| Hybrid routing | **Missing** (v3 sidecar partial) |

**Note:** User-provided **CAI Studio** screenshots (Document AI, Connectors, Prompts, Skills) are **not** implemented in `frontend-dev/`. This repo implements a **custom Next.js Ask Data shell**.

---

## Classification

### KEEP

| Asset | Location |
|-------|----------|
| LangGraph OSSIE workflow | `backend-dev/app/graph/workflow.py` |
| SQL validator (SQLGlot) | `backend-dev/app/sql/validator.py` |
| Semantic resolution / compile | `backend-dev/app/semantic/context.py`, `registry.py` |
| Impala + DuckDB execution adapters | `backend-dev/app/db/*` |
| Chat orchestration + SSE | `backend-dev/app/services/chat.py`, `api/chat.py` |
| Multi-turn history + follow-up | `history.py`, `follow_up.py`, `session_context.py` |
| LLM provider registry | `backend-dev/app/llm/` |
| Usage store + API | `usage_store.py`, `api/usage.py` |
| Disk prompt templates (interim) | `backend-dev/prompts/` |
| Ask Data page + streaming UX | `frontend-dev/src/views/AskDataPage.tsx` |
| Analysis Workspace | `AnalysisReportPanel.tsx`, `analysis/*`, `reportDocument.ts` |
| App shell + white-label config | `AppShell.tsx`, `appConfig.ts`, `BrandMark.tsx` |
| API proxy pattern | `frontend-dev/next.config.mjs`, `lib/api.ts` |
| Vitest + pytest coverage | `frontend-dev/src/**/*.test.*`, `backend-dev/tests/` |
| UAT/eval harness | `backend-dev/eval/`, `scripts/run_uat_*` |
| CAI entrypoints | `app_cai_backend.py`, `app_cai_frontend.py` |

### REFACTOR

| Item | Why |
|------|-----|
| Hardcoded `tempo_scan_impala` | Should be `project_id` from workspace config |
| `Settings.app_name` Tempo strings | Accelerator-neutral defaults |
| `semantic/context.py` FE001 alias | Move to project overlay |
| Impala env in `config.py` | Fold into connector config + SecretProvider |
| `build_query_executor()` in chat | Inject via connector registry |
| FE clarification prompts | Domain pack per project, not core shell |
| localStorage keys `tempo-scan-v2.*` | Configurable namespace |
| Static “Database” chip | Wire to `/health/ready` or remove |
| `docs/api-contract-v2.md` | Superseded by `docs/backend/API_CONTRACT.md` for Ask Data v2 |
| Duplicate `backend/` vs `backend-dev/` | Process: merge policy until M1 |

### DEPRECATE (or isolate to reference)

| Item | Why |
|------|-----|
| `backend-test/` exploratory agent | Different product mode; not governed accelerator path |
| Agent Studio tool paths under `projects/tempo_scan_impala/agent_studio_tools/` | Legacy CAI integration; not dev tree default |
| Optional PuppyGraph stub | Off critical path; keep flag-gated |
| Neo4j ontology mirror (`neo4j_client`, Tempo) | **Out of core accelerator scope** (ADR-007) — optional reference use case only |
| `backend-test/` exploratory stack | **KEEP** isolated reference — not governed accelerator; port 8001 clash |
| `LOCAL_AGENT_PRIMARY` / v3 sidecar as default | Pilot should prefer OSSIE; v3 optional |
| Hardcoded Impala workbench scripts | Dev-only, gitignored patterns |

### NEW (planned M1+)

| Component |
|-----------|
| PostgreSQL metadata + migrations |
| Workspace / project API |
| Knowledge + document ingestion pipeline |
| Qdrant retrieval service |
| Connector registry + Impala/Trino adapters |
| PromptVersion / SkillVersion stores |
| Intent router + hybrid orchestrator |
| Audit event API |
| SecretProvider |
| Capability-driven FE routes (Documents, Connectors, Prompts, Skills) |

---

## Technical debt

1. **Dual backend trees** — drift risk between `backend/` and `backend-dev/`.
2. **SQLite session store** — no workspace isolation; single-file ops limit.
3. **No unified `/api/v1` prefix** — complicates future versioning.
4. **Strategy `unsupported` overload** — used for errors and true unsupported metrics.
5. **Tempo-specific semantic + golden questions** — large YAML coupling in repo.
6. **No integration tests for DuckDB** in CI (seed script manual).
7. **Stream contract** — progress events not formally versioned.
8. **Missing operational audit trail**.
9. **FE type drift** — `exploratory_local` in TS vs backend strategy literals.
10. **Port 8001 clash** — `backend-test` vs `run-dev-stack.sh`.

## Duplication

- Mirror folders: `frontend/` ↔ `frontend-dev/`, `backend/` ↔ `backend-dev/`
- OSSIE copies under both backends
- Overlapping docs at `docs/` root vs new structured folders

## Tests

- **Strong:** semantic resolution, follow-up, workflow, SQL validator, chat API unit tests
- **Weak:** E2E browser, RAG (N/A), connector abstraction (N/A)
- **Live UAT:** YAML-driven scripts requiring Impala/Gemini
