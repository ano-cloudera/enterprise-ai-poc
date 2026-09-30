# TEMPO Scan Commercial Intelligence V2 Design

## Intent and success criteria

TEMPO Scan V2 is a separate Ask Data application pair, not a replacement for V1. It preserves the proven TEMPO visual identity, chat/session experience, governed semantic assets, Impala connectivity, SQL safety, SSE behavior, and CAI deployment pattern while removing Dashboard and Agent Studio from the V2 runtime. A normal analytical request follows a bounded LangGraph workflow with at most two LLM calls: planning/SQL, then result analysis/chart specification.

The deliverable is complete when `frontend-v2` and `backend-v2` start independently, expose the requested APIs, support Qwen/Gemini/OpenAI selection, execute governed and controlled-fallback paths through deterministic validation, stream progress safely, render structured results, and have offline tests that do not require live credentials. V1 files remain behaviorally unchanged.

## Existing artifact reuse plan

| Existing artifact | Location | Decision | V2 use |
|---|---|---|---|
| Next.js shell, styling, chat UI | `frontend/app`, `frontend/src` | ADAPT | Baseline V2 UI; remove Dashboard/Monitoring and dashboard state coupling |
| Recharts/table/KPI components | `frontend/src/components` | REUSE | Declarative `chart_spec`, table, KPI rendering |
| Browser SSE parser | `frontend/src/lib/api.ts` | ADAPT | Preserve final-buffer drain fix; add provider/model per request |
| Browser chat sessions | `frontend/src/lib/chatSessions.ts` | ADAPT | Persist provider/model with each structured response |
| LangGraph workflow | `backend/app/graph`, `backend/app/ossie/graph_nodes.py` | ADAPT | Replace broad V1 routing with explicit V2 state-machine nodes |
| Ossie registry/service | `backend/app/ossie` | REUSE/ADAPT | Semantic context, governed metric compilation, curated schema metadata |
| TEMPO Ossie model/governance | `projects/tempo_scan_impala/ossie` | REUSE | Authoritative metrics, fields, domains, policies, and question source |
| Impala backend + Kerberos | `backend/app/db/impala_backend.py` | REUSE | Read-only execution with existing TLS/HTTP/GSSAPI configuration |
| SQLGlot validator | `backend/app/tools/sql_validator.py` | ADAPT | Validate Ossie-derived table/column allowlists for generated fallback SQL |
| Qwen compatible provider | `backend/app/llm/providers.py` | ADAPT | Common structured-provider contract and Qwen implementation |
| Agent Studio runtime/client | `backend/app/services/agent_studio_*` | DO NOT REUSE | V2 never calls createSession/kickoff/event polling |
| Agent backstories/instructions | `projects/tempo_scan_impala/agents`, project prompts | ADAPT | Versioned V2 planner/analyst/repair system prompts |
| SSE heartbeat route | `backend/app/api/routes/chat.py` | REUSE/ADAPT | Keep 15-second comment heartbeat and no-buffering headers |
| Conversation SQLite store | `backend/app/services/conversation_store.py` | ADAPT | Store user/final response/provider/model, never hidden reasoning |
| CAI entrypoints/scripts | `backend/app_cai_backend.py`, `frontend/app_cai_frontend.py`, `scripts/run-cai-*` | ADAPT | Separate dynamic-port launchers for each V2 application |

## Architecture

`frontend-v2` is a Next.js App Router application with only Ask Data and Settings routes. The browser calls same-origin `/api/*`; Next.js rewrites requests to the configured Backend V2 CAI URL, retaining the proven workaround for CAI cross-origin restrictions. The UI discovers models from `/models`, disables unavailable entries, sends the selected provider/model on every chat request, streams progress through POST SSE, and persists conversations locally.

`backend-v2` is a self-contained FastAPI application. Its LangGraph nodes are:

1. `understand_request` — retrieve semantic/business context and classify clarification/unsupported cases.
2. `plan_query` — resolve a governed metric deterministically where possible; otherwise ask the chosen LLM for a structured controlled-fallback plan using only approved schema context.
3. `validate_query` — validate SELECT-only SQL, tables, columns, limit, and one-statement policy with SQLGlot; permit one structured repair attempt.
4. `execute_query` — run validated SQL through the reused Impala backend and normalize the result.
5. `analyze_result` — ask the same selected provider for a grounded structured answer and declarative chart, or produce a deterministic safe answer when appropriate.

The workflow returns `SUCCESS`, `CLARIFICATION`, `NO_DATA`, `UNSUPPORTED`, or `ERROR`. It emits only named progress stages, not hidden reasoning. Stage durations and provider/model/request/session identifiers are logged as structured fields without credentials.

## Semantic strategies

The governed path uses the existing `TempoOssieService.resolve()` and `compile_query()` output. The controlled SQL fallback is used only when no exact published metric resolves but the requested concepts are covered by the approved Ossie datasets/fields. `SemanticContextService` converts the Ossie model and governance into a compact catalog of allowed physical views, fields, descriptions, aliases, time fields, and explicitly published relationship context. Because the current Ossie file has no relationship objects, fallback joins are denied unless a single published cross-domain view already contains the required fields.

Generated SQL is never executed directly. The V2 validator accepts only one SELECT/WITH query, rejects DDL/DML, `SELECT *`, unknown views/columns/functions, and nonliteral limits, and caps result rows. Credentials and connection configuration never enter prompts.

## Provider boundary

The common provider operation is `generate_structured(messages, response_model, temperature, max_tokens)`. A registry resolves only backend-configured `(provider, model)` pairs:

- Qwen: OpenAI-compatible chat-completions endpoint using `QWEN_BASE_URL`, token, and model.
- Gemini: Google Generative Language REST endpoint using `GEMINI_API_KEY` and `GEMINI_MODEL`.
- OpenAI: chat-completions endpoint using `OPENAI_API_KEY`, optional configurable base URL, and `OPENAI_MODEL`.

Missing credentials or base URLs make a model unavailable in `/models` but never prevent startup. The frontend never sends arbitrary base URLs or API keys. A deterministic mock provider is available only for tests/local validation and is not presented as a production model.

## Contracts and endpoints

- `GET /health` returns exactly `{"status":"ok"}` without external probes.
- `GET /health/ready` reports configured component readiness without leaking secrets.
- `GET /models` returns configured IDs, friendly labels, availability, and safe reasons.
- `GET /random-queries?domain=&difficulty=&limit=` returns curated questions.
- `POST /chat` returns the complete structured response.
- `POST /chat/stream` emits progress events and one terminal response with heartbeat comments.

The response carries answer fields, structured query data, optional chart specification, selected provider/model, strategy, timings, request/session IDs, and normalized status. Chart fields must exist in returned data; invalid chart specifications are dropped.

## Question bank

The bank contains at least 30 questions distributed across Sales/Sell-In, B2B/Sell-Out, Stock Tempo, Stock SAT-IDM, SAT OOS, and cross-domain scenarios. Every question uses metrics/dimensions visible in the current 20-dataset/62-metric Ossie contract. Cross-domain questions use existing published combined views such as `material_360`, `stock_tempo_sales_material_month`, `sales_b2b_material_month`, `b2b_satidm_branch_month`, and `satidm_oos_material_month`; they do not invent relationships.

## Error handling and observability

External and database exceptions are logged server-side with request IDs and normalized to business-safe error responses. Empty result sets become `NO_DATA`; semantic ambiguity becomes `CLARIFICATION`; unavailable concepts become `UNSUPPORTED`. Provider absence/network failure affects only requests selecting that provider. Timing fields are `context_ms`, `planning_ms`, `validation_ms`, `query_ms`, `analysis_ms`, and `total_ms`.

## Deployment

Each V2 directory contains its own dependencies, README, environment example, and CAI entrypoint. Backend binds to the CAI-provided port and host pattern already proven by V1. Frontend uses the proven Python CAI launcher pattern, portable Node fallback, dynamic CAI port, and server-side rewrite; its directory resolution targets `frontend-v2`. Prompt paths resolve from the installed backend package root, never the process working directory.

## Verification

Backend unit/contract tests cover model discovery, all provider adapters, governed/fallback/clarification/no-data/unsupported paths, SQL validation and repair bounds, chart validation, random-query filtering, SSE events, history persistence, and API contracts. Frontend tests cover model discovery/selection, disabled unavailable providers, request payloads, progress/final SSE handling, random question insertion, chat history, and visualization rendering. V1 backend and frontend suites run again after V2 implementation. Optional live provider/database smoke tests run only when safe configuration is present and are reported honestly.
