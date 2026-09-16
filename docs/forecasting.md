# Governed Offline Sales Forecasting

## Architecture

Forecasting is an offline artifact pipeline, never per-question inference:

```text
Governed historical fixtures
  -> monthly aggregation and leakage-safe features
  -> chronological baseline/XGBoost evaluation
  -> approved model metadata and JSON artifact
  -> one-month forecast generation
  -> commercial_sales_forecast
  -> SELECT-only ForecastRepository and ForecastTool
  -> controlled LangGraph forecast branch
  -> Qwen explanation of immutable persisted values
```

The runtime does not import training or writer credentials. If persisted forecast data is missing, the graph returns `FORECAST_NOT_AVAILABLE`; it does not invoke Qwen or extrapolate an estimate.

## Historical data

The existing January–March 2024 daily Tempo fixture remains byte-for-byte unchanged. A compact deterministic monthly fixture adds April 2022–December 2023 at region/product/channel grain. Together they provide 24 chronological months while preserving the existing hero values.

Supported independent forecast series are:

- total
- region
- product
- channel

Sparse cross-dimension combinations are intentionally excluded.

## Features and leakage controls

For each governed series, target-month features include year, month, quarter, monotonic month index, lag 1/2/3, and rolling mean/standard deviation over the three prior actual periods. Rolling and lag features never include the target or a future value. Category codes are derived from deterministically sorted governed series names.

The latest feature-complete month is held out chronologically. Random train/test splitting is prohibited. After evaluation, the XGBoost JSON artifact is retrained on all available history for possible offline inference, while model selection continues to use the held-out metrics.

## Evaluation and model selection

The September 15, 2026 local validation produced:

| Model | MAE | RMSE | Safe MAPE |
|---|---:|---:|---:|
| Lag-1 baseline | 5,906.735 | 7,104.767 | 9.940% |
| XGBoost | 6,679.744 | 8,136.737 | 10.583% |

The active model is therefore `naive_baseline`. XGBoost is not claimed to be superior. Safe MAPE excludes zero-valued actuals. This single synthetic holdout is suitable for architecture validation, not production demand-planning claims.

### External-signal backtest

`scripts/evaluate_external_signals.py` is an offline, read-only comparison of the naive baseline, internal-only XGBoost, and XGBoost with weather, market, or both signal groups. It uses six expanding chronological validation folds. Every external feature is lagged by one month; actual target-month weather and market values are excluded. The market feature set also excludes calibrated price, because its latest digital anchor post-dates the historical forecast window.

The evaluator never writes model artifacts or persisted forecasts. A candidate is recommended only when MAE and RMSE both improve by at least 5%, MAPE does not deteriorate, and it beats the baseline MAE in at least four of six folds. Any recommendation remains subject to an explicit production promotion decision.

## Artifact and generation

Artifacts are written under ignored `artifacts/forecasting/`:

- `sales_forecast_model.json`
- `metadata.json`

Metadata records version, timestamps, history range, validation period, rows, horizon, features, both metric sets, selected model, category encoding, and residual dispersion.

Generation produces April 2024 rows for 1 total, 6 regions, 5 products, and 4 channels. Bounds use the selected model's held-out residual standard deviation:

```text
lower = max(0, forecast - 1.96 × residual_std)
upper = forecast + 1.96 × residual_std
```

This is a deliberately simple PoC interval, not a calibrated probabilistic forecast.

## Canonical forecast table

`commercial_sales_forecast` contains:

```text
forecast_date DATE
generated_at TIMESTAMP locally / ISO VARCHAR for Trino parity
forecast_horizon BIGINT
forecast_sales DOUBLE
lower_bound DOUBLE
upper_bound DOUBLE
model_name VARCHAR
model_version VARCHAR
training_cutoff_date DATE
dimension_type VARCHAR
dimension_value VARCHAR
```

Local generation persists directly through the isolated offline DuckDB writer. The runtime retrieves it only through `QueryService`. `TrinoForecastWriter` is separately scoped to the exact forecast table and must be called by a future Cloudera AI job identity—not the application identity.

## Commands

```bash
.venv/bin/python scripts/train_forecast.py
.venv/bin/python scripts/generate_forecast.py
.venv/bin/python scripts/evaluate_external_signals.py
```

In a future Cloudera AI Workbench job, the same scripts can train and generate, followed by isolated Trino persistence. Scheduling, automatic retraining, MLflow, and online model serving are deliberately outside this milestone.

## Qwen and fallback behavior

Qwen receives the question, resolved forecast intent, persisted forecast rows, and limited model metadata. It may explain direction, bounds, and management meaning. The structured response data is copied from the Forecast Tool and cannot be replaced by model output.

For a missing period, the response includes the requested period, latest configured actual date, `FORECAST_NOT_AVAILABLE`, and an offer to show historical trends. No forecast values or bounds are invented.
