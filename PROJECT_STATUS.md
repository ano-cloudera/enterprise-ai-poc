# Project Status

**Snapshot (9 Oct 2026, PM):** Governed OSSIE/Impala Ask AI on **`backend/` + `frontend/`** is production. **Genie-style Analysis Workspace** (split chat + panel, tabs Summary | Table | Query) is **merged and pushed** (`a213b52` on `origin/main`). Parallel pilot copies **`backend-dev/` + `frontend-dev/`** are in git for UI/API experiments on **3001 / 8001** (`scripts/run-dev-stack.sh`, `docs/analysis-report-dev.md`). UAT baselines unchanged: follow-up **50/50**, 1×2 **10/10**, management **30/30** (`backend/eval/`). OSSIE **24 datasets / 72 metrics**. Exploratory DuckDB sandbox **`backend-test/`** also uses port **8001** — do not run it together with `run-dev-stack.sh`. Typical governed latency **~40–60 s** — see `PROJECT_STATE.md`.

**Latest (9 Oct 2026, PM):** **Analysis Workspace in prod** — `AnalysisReportPanel`, resize split pane, artifact card in chat, Table (rank/sort/CSV) + Query (governed SQL, no meta chips/METRIC block), unified section typography, chart height +15% in workspace; API field **`governed_sql`** on chat response (`backend/app/core/models.py`, `chat.py`; FE `ChatResponse`). Env: `NEXT_PUBLIC_ANALYSIS_REPORT_PANEL` (default on), `NEXT_PUBLIC_LINEAGE_VIEW_URL` optional. **Earlier same day:** Neo4j ontology mirror (optional), matrix routing, narrative chart suppress, Usage tab — still in `PROJECT_STATE.md`.

Foundation architecture updated to v2 after Tempo Scan design review.

Locked:
- LangGraph controlled orchestration, not CrewAI
- Qwen3.8-27B-AWQ + vLLM 0.29.0 serving preserved unchanged
- Next.js frontend target
- FastAPI backend
- YAML + Pydantic semantic layer
- shared conversation/dashboard state
- structured `answer + data + chart_spec + ui_actions + metadata` contract
- fixed UI action whitelist, no arbitrary JavaScript
- deterministic SQL validation before read-only execution
- Guardrails AI additive to deterministic controls

Implemented in foundation:
- v2 backend schemas and LangGraph node sequence
- semantic resolver with follow-up state inheritance
- Result Checker, Visualization Planner, UI Action Generator
- frontend shared dashboard state and action application
- Next.js App Router scaffold
- updated semantic YAML relationships/query rules
- updated architecture, API contract, repository structure, and development sequence docs
- Milestone 1 canonical backend/frontend chat contract and runtime frontend validation
- typed/discriminated UI action payloads with semantic target validation
- central validated query service used by chat and dashboard analytical queries
- hardened table-scoped SQL policy, date rules, limit caps, and safe-function policy
- reproducible Python 3.10/npm dependency locks and verified local startup
- Milestone 2 canonical React Context/reducer dashboard state shared by Dashboard and Ask AI
- centralized dispatcher for all eight validated UI actions, including reset, chart/table state, and visible card highlighting
- AI-applied context chips with manual removal/reset
- context-aware dashboard POST endpoint with governed AST-built filters and date ranges
- project-configured Tempo aliases and deterministic follow-up inheritance/override/reset behavior
- line, bar, area, and pie chat rendering plus safe structured-table fallback
- Milestone 3 Pydantic structured analytical intent and deterministic normalization
- semantic-driven SQLGlot compiler for KPI, trend, breakdown, top/bottom, period comparison, and entity comparison
- controlled result-quality states and grounded mock analysis
- ten executable Tempo Scan golden questions
- Milestone 4 provider-based Qwen CAI analysis integration with strict structured output
- compact trusted analysis payload, bounded retry, deterministic grounded fallback, safe health and model telemetry
- Milestone 5 shared DataBackend result/health contract with DuckDB and Trino adapters
- project-governed `catalog.schema.table` mapping, dual read-only enforcement, dialect rendering, safe data telemetry, and bounded manual Trino probe
- Milestone 5.5 isolated `TRINO_LOADER_*` configuration and allowlisted Trino/CDW bootstrap writer
- deterministic fixture loading in bounded batches, scoped idempotent reload, post-load hero checks, and five-flow DuckDB/Trino parity validation
- Milestone 6A deterministic 24-month forecast history, leakage-safe monthly features, chronological baseline/XGBoost evaluation, and ignored JSON artifacts
- offline one-month forecast generation for total/region/product/channel with governed local persistence and Trino writer readiness
- bounded ForecastRepository/ForecastTool, controlled LangGraph routing, immutable forecast grounding, declarative bounds chart, and non-numeric unavailable fallback

Remaining customer-specific work:
- real Tempo Trino/CDW catalog/schema values, separate loader/runtime credentials, live bootstrap, and live parity verification
- deeper entity resolver/generalized semantic resolution
- richer multi-dataset/join planning beyond the current single-dataset analytical patterns (cross-domain **ratio/journey** metrics shipped; dual-query merged columns not yet)
- production forecast model
- broader real-history forecast validation, calibrated uncertainty, and Cloudera AI job scheduling
- external signals
- golden-question evaluation and monitoring thresholds
- dynamic remapping of the fixed dashboard visuals for arbitrary metric/dimension selections (state is preserved today)

Temporarily disabled:
- baseline forecasting, until it uses the same validated query boundary and a reviewed forecasting model
