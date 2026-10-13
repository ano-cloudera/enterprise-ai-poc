# API Contract — Target & Current

## Versioning strategy

- **Current (stable):** unprefixed routes used by `frontend-dev` — **must remain through M1 and beyond** for chat/models/usage:
  - `POST /chat`, `POST /chat/stream`
  - `GET /models`
  - `GET /usage/summary`, `GET /usage/events`, `GET /usage/export.csv`
- **Target:** new resources under `/api/v1/...` for workspace, project, documents, connectors, prompts, skills, etc.

### M1 routing rule

`/api/v1` handlers **reuse existing services** — e.g. `ChatService.run` / `ChatService.stream`, `ProviderRegistry`, `UsageStore`. They are thin HTTP adapters + auth/context injection, **not** duplicate chat engines or LangGraph graphs.

## Current endpoints (backend-dev)

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/health` | — | `{ "status": "ok" }` |
| GET | `/health/ready` | — | `{ "status": "ready"|"not_ready", "components": {...} }` |
| GET | `/models` | — | `{ "models": ModelInfo[] }` |
| GET | `/random-queries` | `domain?`, `difficulty?`, `limit?` | Question bank slice |
| POST | `/chat` | `AskDataRequest` | `AskDataResponse` |
| POST | `/chat/stream` | `AskDataRequest` | SSE (see below) |
| DELETE | `/chat/sessions/{session_id}` | — | `{ "deleted": n }` |
| GET | `/usage/summary` | `days?`, `mtd?` | `UsageSummary` |
| GET | `/usage/events` | `days?`, `limit?` | events list |
| GET | `/usage/export.csv` | query params | CSV stream |

### M1 platform endpoints (`STATE_STORE=postgres` + `DATABASE_URL`)

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/v1/workspaces` | `{ "workspaces": [...] }` |
| GET | `/api/v1/workspaces/default` | `{ "workspace": {...} }` |
| GET | `/api/v1/projects?workspace_slug=default` | `{ "projects": [...] }` |
| GET | `/api/v1/projects/default` | `{ "project": {...} }` |

Returns **503** when Postgres platform metadata is not configured.

### AskDataRequest (current)

```json
{
  "session_id": "uuid",
  "question": "string",
  "provider": "qwen|gemini|openai",
  "model": "string",
  "use_local_agent": false
}
```

### AskDataResponse (current)

Fields in `backend-dev/app/core/models.py`:

- `request_id`, `session_id`, `status` (`SUCCESS|CLARIFICATION|NO_DATA|UNSUPPORTED|ERROR`)
- `strategy` (`governed|sql_fallback|clarification|unsupported|conversational|...`)
- `answer`: `AnalysisOutput` (direct_answer, executive_summary, insights, business_implications, caveats, data_reference, chart_spec)
- `data`: columns, rows, row_count, execution_ms, governed_metric, unit_format
- `chart_spec`, `timings`, `retry_count`, `usage`, `governed_sql`

## SSE contract (current)

`POST /chat/stream` → `text/event-stream`

- Heartbeat: `: keep-alive` every 15s
- Data lines: JSON object

**Progress event:**

```json
{
  "type": "progress",
  "stage": "string",
  "label": "string",
  "detail": "string|null"
}
```

**Terminal event:**

```json
{
  "type": "done",
  "response": { /* AskDataResponse */ }
}
```

v3 proxy may emit upstream events — treat as implementation detail until unified.

## Target `/api/v1` groups (design)

| Group | Endpoints (illustrative) |
|-------|---------------------------|
| workspaces | `GET/POST /api/v1/workspaces`, `GET/PATCH /api/v1/workspaces/{id}` |
| projects | `.../projects`, bind OSSIE path, default connectors |
| chat | Optional aliases only — **primary chat remains** `/chat`, `/chat/stream` |
| conversations | `GET/DELETE .../conversations`, messages pagination |
| models | `GET /api/v1/models` |
| documents | `POST .../documents/upload`, `GET .../documents/{id}` |
| libraries | CRUD + reindex |
| connectors | CRUD, `POST .../test`, `POST .../sync` |
| prompts | CRUD versions, `POST .../activate` |
| skills | CRUD versions, `POST .../activate` |
| usage | summary, events, export |
| audit | `GET .../audit/events` (admin) |

## Unified AI response (target — not M1 FE migration)

Long term, clients should not branch on internal engine. Proposed superset **`UnifiedAIResponse`**:

```json
{
  "status": "success|clarification|error|no_data",
  "route": "ask_data|rag|hybrid|general|clarification",
  "request_id": "uuid",
  "session_id": "uuid",
  "answer": { "direct_answer": "", "executive_summary": "", "insights": [], "business_implications": [], "caveats": [] },
  "data": { "columns": [], "rows": [], "row_count": 0 },
  "visualization": { "chart_spec": null },
  "citations": [],
  "analysis_document": { "sections": [], "governed_sql": null },
  "clarification": { "question": null, "options": [] },
  "execution_metadata": { "timings": {}, "usage": {}, "strategy": "", "retry_count": 0 },
  "error": { "code": null, "message": null, "safe_message": null }
}
```

**M1 policy:**

- **`AskDataResponse`** on `/chat` and `/chat/stream` remains **unchanged** and is what `frontend-dev` uses.
- **`UnifiedAIResponse`** is documented for future RAG/hybrid clients; backend may add an optional mapper or `/api/v1` responses later **without** forcing FE migration in M1.
- When mapping exists, `AskDataResponse` maps 1:1 into UnifiedAIResponse (empty `citations` until RAG).

## Target SSE events (design)

| type | Purpose |
|------|---------|
| `heartbeat` | keep-alive (optional rename from comment line) |
| `thinking` | optional LLM reasoning indicator |
| `progress` | stage updates (keep current) |
| `clarification` | mid-stream clarify |
| `data` | partial table preview (future) |
| `analysis` | partial narrative (future) |
| `visualization` | chart spec ready |
| `completed` | final unified response |
| `error` | terminal failure |

Preserve compatibility: clients ignoring unknown `type` values.

## Errors

- HTTP 422 — invalid model/provider selection
- HTTP 503 — `/health/ready` not ready
- HTTP 200 + `status: ERROR` — user-safe message in `answer` (data backend failures)

Codes: `IMPALA_*`, `DUCKDB_QUERY_FAILED`, internal `UNEXPECTED`.

## Frontend proxy

Browser → `GET/POST /api/*` → Next rewrite → `BACKEND_API_URL`.

See `frontend-dev/next.config.mjs`.

Legacy doc `docs/api-contract-v2.md` describes an older dashboard/chat shape — **not** the current Ask Data v2 contract.
