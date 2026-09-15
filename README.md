# Enterprise AI PoC Foundation

Reusable Cloudera AI application foundation. Tempo Scan is the first project profile, but the core is intentionally reusable for other PoCs.

## Locked architecture v2

- Next.js + TypeScript + Tailwind frontend
- FastAPI backend
- LangGraph controlled orchestration, not CrewAI
- Qwen3.8-27B-AWQ served by the existing proven vLLM 0.29.0 CAI Application
- Configurable semantic YAML validated by Pydantic
- DuckDB for local development; governed read-only Trino for Cloudera Data Warehouse runtime
- SQL validation before execution, SELECT-only, allowlisted semantic objects, read-only credentials
- Shared conversational + dashboard state
- Structured response: `answer + data + chart_spec + ui_actions + metadata`
- Fixed UI action whitelist, never arbitrary JavaScript
- Guardrails AI as an additive input/output validation layer; deterministic SQL/security controls remain mandatory

## Controlled flow

```text
User Question
  -> Input Guardrail
  -> Intent Router
  -> Semantic Resolver
  -> SQL Generator
  -> SQL Validator
  -> Query Execution
  -> Result Checker
  -> Qwen Analysis
  -> Visualization Planner
  -> UI Action Generator
  -> Output Guardrail
  -> Structured Response
```

The graph has bounded retry only. There is no unrestricted autonomous loop and no database write path.

## AI-driven dashboard behavior

The backend can return allowlisted declarative actions such as:

- `SET_FILTER`
- `SET_DATE_RANGE`
- `CHANGE_METRIC`
- `CHANGE_DIMENSION`
- `RENDER_CHART`
- `SHOW_TABLE`
- `HIGHLIGHT_CARD`
- `RESET_FILTER`

The frontend executes these actions. The LLM never emits code to control the browser.

## Local start

Local development is standardized on Python 3.10. Direct Python dependencies are declared in `backend/requirements.txt` and the fully resolved local/test environment is pinned in `backend/requirements-lock.txt`; optional provider-specific dependency sets extend that lock. Frontend dependency resolution is committed in `frontend/package-lock.json`.

```bash
cp .env.example .env
bash scripts/setup-local.sh
make dev
```

Open:
- UI: `http://127.0.0.1:3000`
- API docs: `http://127.0.0.1:8000/docs`

Default local mode uses:

```env
LLM_MODE=mock
DATA_BACKEND=duckdb
```

After local validation, connect the existing Qwen CAI Application:

```env
LLM_MODE=remote
QWEN_BASE_URL=https://<your-qwen-model-cai-app>/v1
QWEN_MODEL=Qwen3.8-27B-AWQ
QWEN_API_TOKEN=<set-through-local-or-CAI-secrets>
QWEN_DISABLE_THINKING=true
```

Qwen is used only after trusted query execution to produce a schema-validated explanation. SQL generation remains deterministic. The Trino adapter is lazy, independently SELECT-only, and requires an explicitly configured catalog/schema plus read-only runtime identity.

For a bounded Trino connectivity check after setting catalog, schema, user, and one supported secret:

```bash
.venv/bin/python scripts/test_trino_connection.py
```

## Synthetic Tempo bootstrap

Trino demo loading is an explicit operator workflow using a separate loader identity. Preview the exact target and row counts without connecting:

```bash
TRINO_LOADER_CATALOG=<catalog> \
TRINO_LOADER_SCHEMA=<schema> \
.venv/bin/python scripts/bootstrap_trino_demo.py --dry-run
```

With dedicated loader credentials configured:

```bash
.venv/bin/python scripts/bootstrap_trino_demo.py
.venv/bin/python scripts/validate_trino_demo_data.py
```

After validation, configure the separate SELECT-only `TRINO_*` runtime identity and use `DATA_BACKEND=trino make dev`. See `docs/trino-demo-data.md` for the permission boundary and complete workflow.

## Offline forecasting

Milestone 6A adds one-month total/region/product/channel forecasts without online ML inference:

```bash
.venv/bin/python scripts/train_forecast.py
.venv/bin/python scripts/generate_forecast.py
```

The scripts evaluate XGBoost against lag-1 chronologically and promote the better model. The application only queries persisted `commercial_sales_forecast` rows through the governed Forecast Tool. Missing forecasts return `FORECAST_NOT_AVAILABLE` and are never estimated by Qwen. See `docs/forecasting.md`.

## Key docs

- `docs/architecture.md`
- `docs/api-contract-v2.md`
- `docs/repository-structure-v2.md`
- `docs/development-sequence-v2.md`
- `docs/semantic-layer.md`
- `docs/nl-to-sql.md`
- `docs/golden-questions.md`
- `docs/qwen-integration.md`
- `docs/health.md`
- `docs/trino-demo-data.md`
- `docs/forecasting.md`
- `PROJECT_STATUS.md`

## Important boundary

`model-serving/reference-vllm/` is a frozen reference snapshot of the already proven model-serving implementation. Do not rebuild or replace the running Qwen/vLLM CAI Application from this folder unless there is a separate technical reason.
# enterprise-ai-poc
