# Milestone 6B: Product Alignment and Historical Weather Signal

## Constraints

- Preserve the deterministic historical SQL path, Milestone 6A forecast pipeline, and model-serving implementation.
- Keep weather out of forecast features and prohibit arbitrary generated joins.
- Persist weather locally only; do not write to live Trino.
- Treat representative-city weather as a documented PoC proxy for each commercial region.

## TDD sequence

1. Add failing tests for governed product families/categories while pinning the Jawa Barat hero totals and forecast regressions.
2. Add failing tests for project-configured region/location mappings and validated Open-Meteo normalization.
3. Add failing tests for deterministic daily-to-monthly aggregation and idempotent DuckDB persistence.
4. Add failing tests for governed sales/weather comparisons, correlation thresholds, and missing-signal fallback.
5. Add failing tests for controlled historical/forecast/weather routing and evidence-safe explanation behavior.
6. Add at least eight project-owned weather golden questions and validate their deterministic resolution.
7. Implement the minimum product configuration, weather provider boundary, service, repository, ingestion script, graph route, and response shaping required to pass each test group.
8. Run the complete backend suite, bundle validation, forecast regression, and frontend checks.
9. If network access is available, run historical Open-Meteo ingestion into local DuckDB and report coverage/sample evidence. Never persist to Trino in this milestone.

## Design

- `projects/tempo_scan/config.yaml` owns representative products and commercial-region-to-weather-location mappings.
- `app.external_signals.weather` owns API-neutral models, provider protocol, Open-Meteo adapter, aggregation, local repository, and deterministic analysis service.
- The weather tool accepts only governed region/period intent and emits structured calculated evidence.
- LangGraph routes weather questions directly to the deterministic weather tool. Qwen can only explain immutable evidence; fallback text is deterministic and explicitly non-causal.
- `commercial_weather_monthly` is replaced/upserted by its natural key `(period, region_name, source)` for idempotency.

## Verification

- `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests`
- `.venv/bin/python scripts/validate_bundle.py`
- Existing forecast train/generate regression checks
- Frontend lint/build/tests defined by the existing package scripts
- Optional live execution of `scripts/fetch_weather_history.py` against Open-Meteo, local persistence only
