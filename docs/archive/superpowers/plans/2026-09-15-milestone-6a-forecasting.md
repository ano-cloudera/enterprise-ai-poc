# Milestone 6A Implementation Plan: Governed Offline Sales Forecasting

Date: 2026-09-15

## Non-negotiable boundaries

- Training and inference run only as explicit offline scripts.
- Online requests only retrieve persisted `commercial_sales_forecast` rows.
- `QueryService` and runtime `TrinoBackend` remain SELECT-only.
- Forecast writes use a separate isolated writer boundary and credentials.
- Qwen may explain persisted values but cannot generate or alter forecast numbers.
- DuckDB/mock mode remains the default and automated tests require no live CDW access.

## Task 1 — Historical coverage and deterministic fixture

1. Add failing tests for deterministic 24-month monthly coverage and preservation of the existing February/March hero values.
2. Add a compact project-owned `commercial_sales_monthly_history.csv` covering April 2022–December 2023 at month/region/product/channel grain.
3. Extend `generate_sample_data.py` to reproduce that file with an isolated seed while preserving the existing daily fixture byte-for-byte for January–March 2024.
4. Verify bundle and historical golden questions.

## Task 2 — Forecasting domain contracts and feature engineering

1. Add failing tests for canonical forecast rows/metadata, lag-1/2/3, rolling mean/std, deterministic output, and absence of future leakage.
2. Add `backend/app/forecasting/models.py` and `features.py`.
3. Aggregate daily data and combine it with the compact historical fixture.
4. Support only total, region, product, and channel series.

## Task 3 — Evaluation and chronological training

1. Add failing tests for MAE, RMSE, safe MAPE, chronological split, baseline predictions, XGBoost training, and model selection.
2. Add `evaluation.py` and `training.py` using the low-level CPU XGBoost API.
3. Hold out the latest feature-complete month; never use random splitting.
4. Evaluate lag-1 and XGBoost honestly and persist the winning model choice.
5. Save small JSON model/metadata artifacts under ignored `artifacts/forecasting/`.

## Task 4 — Offline forecast generation and persistence

1. Add failing tests for one-month horizon, deterministic predictions, uncertainty ordering, model version/cutoff, and local persistence.
2. Add `inference.py` and a local DuckDB forecast store.
3. Persist canonical `commercial_sales_forecast` rows.
4. Add an isolated Trino forecast writer that can target only that table and never imports runtime credentials.

## Task 5 — Governed forecast repository and tool

1. Add failing tests for total/region/product/channel filtering, latest-version selection, and unavailable periods.
2. Add `repository.py` and a bounded `get_sales_forecast` tool with typed arguments only.
3. Return `FORECAST_NOT_AVAILABLE` with latest forecast/actual context; never synthesize values.

## Task 6 — Controlled LangGraph forecast branch

1. Add failing routing tests for forecast wording, historical regression, and inherited dashboard filters.
2. Replace the disabled forecast response with deterministic intent resolution, repository lookup, result checking, grounded explanation, declarative chart spec, and existing UI actions.
3. Ensure Qwen receives only persisted forecast/tool results and cannot overwrite numeric fields.

## Task 7 — Project configuration and golden questions

1. Add the governed forecast semantic dataset and its exact DuckDB/Trino table mapping.
2. Add eight project-owned forecast questions plus an unavailable-period case.
3. Keep existing analytical semantic definitions unchanged.

## Task 8 — Scripts, documentation, and verification

1. Add `scripts/train_forecast.py`, `generate_forecast.py`, and a concise optional validator.
2. Add `docs/forecasting.md`; update README, architecture, status, and manifest.
3. Run backend tests, bundle validation, training, generation, frontend tests/build, and five required API smoke flows.
4. Clearly distinguish automated/local results from unverified live Trino persistence.

## Logical commit checkpoints

1. `docs: plan governed offline forecasting milestone`
2. `feat: add deterministic forecast features and evaluation`
3. `feat: add offline xgboost training and forecast persistence`
4. `feat: add governed forecast retrieval and graph routing`
5. `docs: document forecasting workflow and validation`
