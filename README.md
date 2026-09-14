# Enterprise AI PoC Foundation

Reusable Cloudera AI application foundation. Tempo Scan is the first project profile, but the core is intentionally reusable for other PoCs.

## Locked architecture v2

- Next.js + TypeScript + Tailwind frontend
- FastAPI backend
- LangGraph controlled orchestration, not CrewAI
- Qwen3.8-27B-AWQ served by the existing proven vLLM 0.29.0 CAI Application
- Configurable semantic YAML validated by Pydantic
- DuckDB for local development, Impala/CDW as trusted production-like query source
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
LLM_BASE_URL=https://<your-qwen-model-cai-app>
LLM_MODEL=/home/cdsw/models/Qwen3.8-27B-AWQ
```

Then switch trusted data to Impala/CDW with a read-only credential.

## Key docs

- `docs/architecture.md`
- `docs/api-contract-v2.md`
- `docs/repository-structure-v2.md`
- `docs/development-sequence-v2.md`
- `PROJECT_STATUS.md`

## Important boundary

`model-serving/reference-vllm/` is a frozen reference snapshot of the already proven model-serving implementation. Do not rebuild or replace the running Qwen/vLLM CAI Application from this folder unless there is a separate technical reason.
# enterprise-ai-poc
