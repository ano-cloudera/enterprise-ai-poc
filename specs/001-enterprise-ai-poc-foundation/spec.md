# Feature Specification: Reusable Enterprise AI PoC Foundation

## Problem

Teams need a reusable Cloudera AI application foundation that can move quickly from a customer use case to a credible management demo without rebuilding model serving, orchestration, semantic modeling, security, monitoring, and frontend patterns each time.

## Primary user story

As a business leader, I can ask a natural-language question about governed company data and receive a concise executive answer with traceable key drivers, recommended actions, and a chart.

## Tempo Scan acceptance scenario

Given synthetic sales and inventory data for Jan-Mar 2024,
when the user asks `Kenapa sales Jawa Barat turun bulan ini?`,
the application must:

1. classify the question as analytical;
2. load the Tempo semantic model;
3. generate one read-only SELECT query;
4. reject non-allowlisted or write SQL;
5. execute against the trusted local dataset;
6. provide the query result to Qwen, not raw database credentials;
7. return Executive Summary, Key Drivers, Recommended Actions;
8. include a chart when the result is chartable;
9. include a trace id, validation status, row count, backend, model and latency;
10. never expose chain-of-thought.

## Functional requirements

- FR-001: App supports project profiles under `projects/<project_id>`.
- FR-002: Core frontend offers Dashboard, Ask AI, Settings, AI Monitoring.
- FR-003: Backend exposes stable API contracts independent of customer schema.
- FR-004: Semantic layer is editable without changing orchestration code.
- FR-005: SQL is single-statement SELECT only with allowlisted tables and row limits.
- FR-006: Data access remains behind a generic backend; DuckDB is local and Trino/CDW is the planned Milestone 5 production adapter. The existing Impala scaffold is compatibility-only.
- FR-007: LLM backend can switch between mock and remote OpenAI-compatible endpoint.
- FR-008: Reasoning/thinking output is never returned to the end user.
- FR-009: Input/output fallback is controlled and non-fabricating.
- FR-010: Telemetry persists locally for PoC monitoring.
- FR-011: Forecast path exists as a bounded foundation path but is clearly labeled baseline until validated.
- FR-012: Existing Qwen/vLLM model-serving snapshot is preserved, not rewritten.

## UX requirements

- Dominant white/off-white surfaces
- Cloudera orange and deep navy/violet accents
- Executive-friendly density
- Responsive layout
- Clear data-grounding / system-status cues
- Technical trace is collapsed by default
- No chat-only experience; dashboard and metrics remain first-class

## Out of scope for this feature

Real Tempo data mapping, production IAM/TLS/HA, validated forecasting model, external market data, production-quality hallucination score, and customer production sizing.

## Architecture Amendment v2

The primary orchestrator SHALL be LangGraph. CrewAI SHALL NOT be used for the Tempo baseline. The chat response SHALL expose `answer`, `data`, `chart_spec`, `ui_actions`, and `metadata`. UI actions SHALL be limited to a fixed schema and SHALL NOT contain arbitrary executable frontend code. Follow-up turns SHALL accept prior dashboard state so conversational state and dashboard state remain aligned.
