# TEMPO Scan V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver separate, production-oriented `frontend-v2` and `backend-v2` applications by adapting proven TEMPO V1 artifacts into a two-call controlled LangGraph Ask Data workflow.

**Architecture:** A self-contained FastAPI backend uses Ossie-first resolution, controlled approved-schema SQL fallback, SQLGlot validation, Impala execution, and provider-neutral structured generation. A pruned Next.js frontend retains the existing chat/session/visualization experience and communicates through the existing CAI-safe same-origin rewrite and SSE pattern.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, LangGraph, SQLGlot, Impyla, httpx, pytest; Next.js 15, React 19, TypeScript, Recharts, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-30-tempo-scan-v2-design.md`

## Global Constraints

- V1 source behavior must remain unchanged; all product changes live in `frontend-v2`, `backend-v2`, and V2 documentation.
- Reuse the current 20-dataset/62-metric `tempo_scan_impala` Ossie contract and existing Impala Kerberos/TLS configuration.
- Agent Studio, CrewAI, and autonomous agent loops are forbidden in V2 runtime.
- Normal analytical execution uses at most two LLM calls plus at most one SQL repair attempt.
- SQL execution is read-only, single-statement, approved-view/column bounded, limited, and deterministic.
- Provider credentials and connection secrets never reach the frontend, prompts, responses, or logs.
- External provider credentials are optional at startup and optional integration tests must skip honestly.

## Review Focus

- An arbitrary frontend model ID must be rejected even when its provider is valid; Task 1 API tests pin allowlist behavior.
- A fallback query that references an allowed column on the wrong table must be rejected; Task 2 validator tests pin table-scoped fields.
- An SSE final frame delivered with the final network chunk must still render; Task 4 API parser test pins buffer draining.
- A chart referencing absent result fields must be removed rather than rendered incorrectly; Task 3 workflow tests pin chart normalization.
- Missing Gemini/OpenAI credentials must not fail backend startup or enable their UI options; Tasks 1 and 4 test both boundaries.

---

### Task 1: Backend V2 foundation and provider registry

**Files:**
- Create: `backend-v2/app/core/config.py`, `backend-v2/app/core/models.py`, `backend-v2/app/llm/base.py`, `backend-v2/app/llm/providers.py`, `backend-v2/app/llm/registry.py`, `backend-v2/app/main.py`, `backend-v2/app/api/models.py`, `backend-v2/tests/test_models_api.py`, `backend-v2/tests/test_providers.py`
- Reuse: relevant package markers, requirements, safe error middleware, and V1 provider HTTP conventions

**Interfaces:**
- Produces: `ProviderRegistry.list_models()`, `ProviderRegistry.resolve(provider, model)`, `LLMProvider.generate_structured(...)`, `GET /models`, lightweight `GET /health`.

- [x] Write provider/model discovery and contract tests, including unavailable optional providers and arbitrary-model rejection.
- [x] Run focused tests and observe expected import/route failures.
- [x] Implement settings, provider adapters, registry, app factory, and safe model/health routes.
- [x] Run focused tests and confirm pass.

### Task 2: Semantic context, SQL policy, and question bank

**Files:**
- Create: `backend-v2/app/semantic/context.py`, `backend-v2/app/semantic/questions.py`, `backend-v2/app/sql/validator.py`, `backend-v2/app/api/random_queries.py`, `backend-v2/data/random_queries.yaml`, `backend-v2/projects/tempo_scan_impala/**`, `backend-v2/tests/test_semantic_context.py`, `backend-v2/tests/test_sql_validator.py`, `backend-v2/tests/test_random_queries.py`
- Reuse/adapt: V1 Ossie registry/service, Ossie YAML/governance/golden questions, SQLGlot policy, Impala backend primitives.

**Interfaces:**
- Consumes: configuration from Task 1.
- Produces: `SemanticContextService`, `ValidatedSQL`, `validate_sql(sql, context)`, `QuestionBank.query(...)`, `GET /random-queries`.

- [x] Write failing tests for context extraction, approved-table/column validation, unsafe SQL, limit capping, 30-question distribution, and endpoint filters.
- [x] Run focused tests and confirm expected failures.
- [x] Copy the semantic contract and implement the context, validator, curated question bank, and endpoint.
- [x] Run focused tests and confirm pass.

### Task 3: Controlled LangGraph workflow, persistence, and SSE API

**Files:**
- Create: `backend-v2/app/graph/state.py`, `backend-v2/app/graph/nodes.py`, `backend-v2/app/graph/workflow.py`, `backend-v2/app/services/chat.py`, `backend-v2/app/services/history.py`, `backend-v2/app/api/chat.py`, `backend-v2/prompts/*.md`, `backend-v2/tests/test_workflow.py`, `backend-v2/tests/test_chat_api.py`, `backend-v2/tests/test_history.py`
- Reuse/adapt: V1 governed query compiler, Impala client, conversation SQLite store, structured output prompts/backstories, SSE heartbeat route.

**Interfaces:**
- Consumes: provider registry, semantic context, SQL validator, question bank.
- Produces: typed `AskDataState`, compiled `workflow`, `ChatService.run/stream`, `POST /chat`, `POST /chat/stream`.

- [x] Write failing tests for governed, fallback, clarification, unsupported, invalid/repair, no-data, chart validation, timings, history, and SSE stage/final events.
- [x] Run focused tests and confirm failures are feature-missing failures.
- [x] Implement the bounded nodes and service with at most two normal LLM calls and one repair.
- [x] Run focused tests and full Backend V2 suite.

### Task 4: Frontend V2 Ask Data application

**Files:**
- Create/adapt: `frontend-v2/app/**`, `frontend-v2/src/**`, `frontend-v2/package*.json`, Next/Tailwind/TypeScript/Vitest configs and tests.
- Reuse/adapt: V1 layout/branding, Ask AI view, sessions, API/SSE parser, Recharts/table/KPI components.

**Interfaces:**
- Consumes: `/models`, `/random-queries`, `/chat/stream` contracts from Tasks 1–3.
- Produces: Ask Data root, Settings model selector, random question action, persistent provider/model per session, structured visual rendering.

- [x] Mechanically fork reusable frontend files without build artifacts or dependencies.
- [x] Write failing tests for V2 navigation, discovered model selector, unavailable models, model-bearing chat request, random questions, history, and final-chunk SSE handling.
- [x] Run focused tests and confirm expected failures.
- [x] Remove dashboard/monitoring coupling and implement V2 API/UI behavior.
- [x] Run Frontend V2 tests, type/build checks, and verify no network-dependent font fetch.

### Task 5: CAI deployment artifacts and documentation

**Files:**
- Create: `backend-v2/app_cai_backend.py`, `backend-v2/start.sh`, `backend-v2/.env.example`, `backend-v2/README.md`, `frontend-v2/app_cai_frontend.py`, `frontend-v2/start.sh`, `frontend-v2/.env.example`, `frontend-v2/README.md`.
- Adapt: V1 dynamic ports, path discovery, dependency installation, proxy configuration, log handling, and CAI environment conventions.

**Interfaces:**
- Consumes: runnable backend/frontend from prior tasks.
- Produces: standalone launch commands and complete deployment/environment guidance.

- [x] Add smoke tests that launch/import entrypoints with controlled environment and validate dynamic port/config failures.
- [x] Run smoke tests and confirm expected failures.
- [x] Implement launchers and deployment guides using V1 patterns.
- [x] Run startup/health smoke checks locally.

### Task 6: Regression, optional live probes, and final audit

**Files:**
- Modify only V2 tests/docs if verification reveals defects.

**Interfaces:**
- Consumes: complete V2 applications.
- Produces: verified test/build record and explicit live-test limitations.

- [x] Run full Backend V2 and Frontend V2 suites plus compile/type/build checks.
- [x] Run V1 backend and frontend test suites to prove behavior preservation.
- [x] Probe configured providers/Impala only when the necessary safe configuration and network are available; otherwise record exact skipped reasons.
- [x] Audit `git diff`, secrets, V2 runtime imports, endpoint list, question counts, prompt packaging, and CAI docs against the spec.

Verification record (2026-09-30): Backend V2 `40 passed`; Frontend V2 `8 passed`; Frontend V2 production build and Python compilation passed; V1 backend `454 passed`; V1 frontend `71 passed`; deployment dry-runs `3 passed`; `/health`, `/models`, and `/random-queries` smoke requests returned HTTP 200. Live provider and Impala probes were skipped because no complete V2 provider/model pair or Impala host/Kerberos configuration was available in the process environment; no model IDs or connection values were invented.
