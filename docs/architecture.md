# Architecture Plan v2

## Locked decisions

- Frontend target: Next.js + TypeScript + Tailwind, production-style Cloudera-inspired UI.
- Backend: FastAPI.
- Orchestration: LangGraph. CrewAI is intentionally not used.
- LLM: existing Qwen3.8-27B-AWQ serving through the proven vLLM 0.29.0 CAI Application. Do not rebuild it.
- Semantic layer: configurable YAML validated by Pydantic.
- Trusted data: DuckDB locally; Trino for Cloudera Data Warehouse is the Milestone 5 production target.
- SQL execution: SELECT-only, allowlisted semantic objects, validated before execution, read-only credentials.
- Query boundary: every analytical query, including dashboard queries, passes through `QueryService.execute_validated` before a backend adapter is called.
- UI control: declarative allowlisted `ui_actions`; the model never returns arbitrary JavaScript.
- Visualization: frontend-rendered chart specs using Recharts/ECharts-class components. Third-party BI is optional, not a dependency.
- Guardrails: deterministic backend controls first, Guardrails AI additive for input/output validation.

## Runtime flow

```text
User Question
  -> Input Guardrail
  -> Intent Router
  -> Semantic Resolver
  -> Structured Analytical Intent Normalizer
  -> SQL Generator
  -> SQL Validator
  -> DataBackend Query Execution (DuckDB local; Trino/CDW runtime)
  -> Result Checker
  -> Qwen Analysis
  -> Visualization Planner
  -> UI Action Generator
  -> Output Guardrail
  -> Structured Response
```

No unrestricted autonomous loop is allowed. SQL repair is bounded. Database write access does not exist.

Qwen is isolated to the post-query analysis node. It receives a compact payload containing the question, normalized intent, only relevant metric/dimension definitions, and validated query rows. It cannot generate or execute SQL, select tools, or alter workflow state. Provider failure is recoverable and produces a deterministic result-grounded summary.

```text
DataBackend
├── DuckDBBackend       # local/test
└── TrinoBackend        # remote Cloudera Data Warehouse, read-only
```

The existing Impala adapter scaffold is retained for compatibility but is no longer described as the final CDW integration target.

```text
Development: Next.js -> FastAPI -> LangGraph -> QueryService -> DuckDB
Target PoC:  Next.js -> FastAPI -> LangGraph -> QueryService -> Trino -> Cloudera Data Warehouse
Model path:  FastAPI -> Qwen CAI Application
```

The data and model paths are independent remote dependencies. Neither is contacted at module import or required for default local startup. Trino SQL is rendered from the same semantic SQL AST as DuckDB SQL, then independently checked by the SQL validator and the defensive read-only Trino adapter.

The Python client applies `TRINO_CONNECT_TIMEOUT_SECONDS` and `TRINO_QUERY_TIMEOUT_SECONDS` as the HTTP connect/read timeout tuple. This bounds individual coordinator requests; it is not an end-to-end server-side query deadline. The adapter does not claim cancellation beyond the driver behavior.

## Synthetic data bootstrap boundary

```text
Deterministic Tempo CSV fixtures
  -> scripts/bootstrap_trino_demo.py
  -> isolated loader config and allowlisted writer
  -> Trino/CDW governed tables
  -> separate SELECT-only runtime identity
  -> QueryService -> TrinoBackend -> LangGraph/Qwen/UI
```

Write capability exists only under `backend/app/bootstrap/` and its operator scripts. It is not imported by FastAPI runtime services. Loader credentials use the `TRINO_LOADER_*` namespace and never fall back to application `TRINO_*` credentials.

## Offline forecast path

```text
Historical sales -> offline feature engineering -> baseline/XGBoost evaluation
  -> persisted commercial_sales_forecast -> ForecastRepository -> ForecastTool
  -> controlled LangGraph forecast branch -> Qwen explanation -> structured response
```

No model inference occurs in FastAPI request handling. The offline writer is separate from the SELECT-only runtime, and missing forecast rows terminate in a controlled non-numeric fallback.

In local mock mode, the SQL generator is a deterministic compiler from the normalized Pydantic analytical intent plus the validated semantic project. It does not derive identifiers, filters, joins, or ordering directly from raw question text. SQLGlot constructs the query AST, and the existing SQL validator remains authoritative before the central QueryService can execute it.

## Shared conversational + dashboard state

Frontend sends the latest dashboard state on every chat request. The semantic resolver combines that state with the new utterance.

Example:

```text
Turn 1: "Kenapa sales Jawa Barat turun bulan ini?"
state => region=Jawa Barat, period=current_month, metric=net_sales

Turn 2: "Kalau cuma Modern Trade?"
state => region=Jawa Barat, channel=Modern Trade, period=current_month, metric=net_sales
```

The backend returns both a resolved state and allowlisted `ui_actions`. Frontend owns execution of those actions.

The frontend keeps one browser-session state in React Context backed by a reducer. Both Dashboard and Ask AI consume it. Responses pass through the runtime contract validator before the centralized UI action dispatcher mutates state; page components do not interpret raw actions. The dashboard posts this state to `/api/dashboard/overview` whenever its revision changes.

Dashboard SQL starts from project-owned query templates. The service validates filter names and values against the semantic project, adds predicates with the SQL AST, and sends every resulting query through the central validated query boundary. Metric and dimension selections are preserved in shared state; the current fixed Tempo dashboard visuals do not yet remap their measures or grouping dynamically.

## UI action whitelist

- `SET_FILTER`
- `SET_DATE_RANGE`
- `CHANGE_METRIC`
- `CHANGE_DIMENSION`
- `RENDER_CHART`
- `SHOW_TABLE`
- `HIGHLIGHT_CARD`
- `RESET_FILTER`

Any unknown action fails contract validation.
