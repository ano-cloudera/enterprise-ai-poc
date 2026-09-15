# Bundle Manifest v2

## Core
- `backend/`: FastAPI + LangGraph controlled orchestration
- `backend/app/services/query.py`: mandatory validation and execution boundary for analytical SQL
- `backend/app/bootstrap/`: isolated write-capable demo bootstrap and validation boundary; never part of runtime QueryService
- `backend/app/forecasting/`: offline feature/training/inference/writer modules plus runtime retrieval-only repository/tool
- `frontend/`: Next.js App Router frontend
- `projects/tempo_scan/`: Tempo-specific semantic config, branding, prompts, fixtures
- `projects/_template/`: reusable customer profile template

## Architecture additions in v2
- shared dashboard/conversation state
- Semantic Resolver node
- Result Checker node
- Visualization Planner node
- UI Action Generator node
- fixed UI action whitelist
- v2 structured frontend/backend contract
- semantic YAML relationships, allowed fields, and query rules
- Pydantic structured analytical intent and deterministic SQLGlot compiler
- generic mock/Qwen analysis providers with compact trusted payloads
- bounded model retry, grounded fallback, safe health, and model telemetry
- normalized DuckDB/Trino DataBackend contract and governed read-only Trino adapter
- `scripts/test_trino_connection.py` bounded manual probe and `docs/trino-demo-data.md` loader/runtime separation
- `scripts/bootstrap_trino_demo.py`: dry-run and explicit two-table CDW bootstrap
- `scripts/validate_trino_demo_data.py`: live table, hero-story, and five-flow parity validation
- `scripts/train_forecast.py`: chronological lag-1/XGBoost training and evaluation
- `scripts/generate_forecast.py`: one-month governed forecast generation and local persistence

## Preserved unchanged
- `model-serving/reference-vllm/`: proven Qwen/vLLM reference snapshot
- `gradio-test/`: engineering test harness

## Documentation
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
