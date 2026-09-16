from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from math import ceil
from pathlib import Path
from statistics import mean

import duckdb
import xgboost as xgb

from app.forecasting.evaluation import calculate_metrics
from app.forecasting.models import EvaluationMetrics, FeatureRow
from app.forecasting.training import FEATURE_NAMES, category_codes, feature_matrix


MODEL_VARIANTS = (
    "naive_baseline",
    "xgboost_internal_only",
    "xgboost_weather",
    "xgboost_market",
    "xgboost_weather_market",
)

WEATHER_FEATURE_NAMES = (
    "weather_lag_1_temperature",
    "weather_lag_1_precipitation",
    "weather_lag_1_humidity",
    "weather_lag_1_rainy_days",
)
MARKET_FEATURE_NAMES = (
    "market_lag_1_growth",
    "market_lag_1_share",
    "market_lag_1_distribution",
    "market_lag_1_competitive_pressure",
)


@dataclass(frozen=True)
class ExternalSignalStore:
    weather_national: dict[date, tuple[float, ...]]
    weather_by_region: dict[tuple[date, str], tuple[float, ...]]
    market_national: dict[date, tuple[float, ...]]
    market_by_region: dict[tuple[date, str], tuple[float, ...]]
    market_by_product: dict[tuple[date, str], tuple[float, ...]]


@dataclass(frozen=True)
class BacktestVariantResult:
    variant: str
    metrics: EvaluationMetrics
    improvement_vs_current_pct: float
    fold_wins: int


@dataclass(frozen=True)
class ExternalSignalBacktestReport:
    results: tuple[BacktestVariantResult, ...]
    best_model: str
    best_improvement_pct: float
    replace_current: bool
    reason: str
    validation_months: tuple[date, ...]


def _previous_month(value: date) -> date:
    return date(value.year - (value.month == 1), 12 if value.month == 1 else value.month - 1, 1)


def chronological_backtest_months(features: list[FeatureRow], fold_count: int = 6) -> list[date]:
    months = sorted({row.month for row in features})
    if fold_count < 1 or len(months) <= fold_count:
        raise ValueError("Backtest needs training history before every validation fold")
    return months[-fold_count:]


def _average(values: list[tuple[float, ...]]) -> tuple[float, ...]:
    return tuple(mean(column) for column in zip(*values))


def load_external_signal_store(path: str | Path) -> ExternalSignalStore:
    with duckdb.connect(str(path), read_only=True) as connection:
        weather = connection.execute(
            "SELECT period, region_name, avg_temperature_c, total_precipitation_mm, "
            "avg_relative_humidity_pct, rainy_days FROM commercial_weather_monthly ORDER BY period, region_name"
        ).fetchall()
        market = connection.execute(
            "SELECT period, region_name, product_name, market_growth_pct, market_share_pct, "
            "distribution_coverage_pct, competitive_pressure_index "
            "FROM commercial_market_monthly ORDER BY period, region_name, product_name"
        ).fetchall()
    if not weather or not market:
        raise ValueError("Weather and calibrated market history are required for the external-signal backtest")

    weather_by_region = {
        (row[0], row[1]): tuple(float(value) for value in row[2:]) for row in weather
    }
    weather_groups: dict[date, list[tuple[float, ...]]] = defaultdict(list)
    for (period, _), values in weather_by_region.items():
        weather_groups[period].append(values)

    market_region_groups: dict[tuple[date, str], list[tuple[float, ...]]] = defaultdict(list)
    market_product_groups: dict[tuple[date, str], list[tuple[float, ...]]] = defaultdict(list)
    market_national_groups: dict[date, list[tuple[float, ...]]] = defaultdict(list)
    for period, region, product, *values in market:
        numeric = tuple(float(value) for value in values)
        market_region_groups[(period, region)].append(numeric)
        market_product_groups[(period, product)].append(numeric)
        market_national_groups[period].append(numeric)

    return ExternalSignalStore(
        weather_national={key: _average(values) for key, values in weather_groups.items()},
        weather_by_region=weather_by_region,
        market_national={key: _average(values) for key, values in market_national_groups.items()},
        market_by_region={key: _average(values) for key, values in market_region_groups.items()},
        market_by_product={key: _average(values) for key, values in market_product_groups.items()},
    )


def signal_features(
    row: FeatureRow, store: ExternalSignalStore, *, use_weather: bool, use_market: bool,
) -> list[float]:
    # Only t-1 signals may describe target month t. This deliberately excludes
    # actual weather and calibrated market values from the validation month.
    signal_month = _previous_month(row.month)
    values: list[float] = []
    if use_weather:
        weather = (
            store.weather_by_region.get((signal_month, row.dimension_value))
            if row.dimension_type == "region" else store.weather_national.get(signal_month)
        )
        if weather is None:
            raise ValueError(f"Missing lagged weather signal for {row.month}")
        values.extend(weather)
    if use_market:
        if row.dimension_type == "region":
            market = store.market_by_region.get((signal_month, row.dimension_value))
        elif row.dimension_type == "product":
            market = store.market_by_product.get(
                (signal_month, row.dimension_value), store.market_national.get(signal_month),
            )
        else:
            market = store.market_national.get(signal_month)
        if market is None:
            raise ValueError(f"Missing lagged market signal for {row.month}")
        values.extend(market)
    return [float(value) for value in values]


def _variant_flags(variant: str) -> tuple[bool, bool]:
    return variant in {"xgboost_weather", "xgboost_weather_market"}, variant in {
        "xgboost_market", "xgboost_weather_market",
    }


def _matrix(
    rows: list[FeatureRow], type_codes: dict[str, int], value_codes: dict[str, int],
    store: ExternalSignalStore, variant: str,
) -> tuple[list[list[float]], list[str]]:
    use_weather, use_market = _variant_flags(variant)
    base = feature_matrix(rows, type_codes, value_codes)
    values = [
        internal + signal_features(row, store, use_weather=use_weather, use_market=use_market)
        for row, internal in zip(rows, base)
    ]
    names = list(FEATURE_NAMES)
    if use_weather:
        names.extend(WEATHER_FEATURE_NAMES)
    if use_market:
        names.extend(MARKET_FEATURE_NAMES)
    return values, names


def _predict_fold(
    train: list[FeatureRow], validation: list[FeatureRow], type_codes: dict[str, int],
    value_codes: dict[str, int], store: ExternalSignalStore, variant: str,
) -> list[float]:
    train_values, names = _matrix(train, type_codes, value_codes, store, variant)
    validation_values, _ = _matrix(validation, type_codes, value_codes, store, variant)
    train_matrix = xgb.DMatrix(train_values, label=[row.target for row in train], feature_names=names)
    validation_matrix = xgb.DMatrix(validation_values, feature_names=names)
    booster = xgb.train(
        {
            "objective": "reg:squarederror", "tree_method": "hist", "max_depth": 3,
            "eta": 0.05, "subsample": 1.0, "colsample_bytree": 1.0,
            "seed": 42, "nthread": 1,
        },
        train_matrix,
        num_boost_round=120,
    )
    return [max(0.0, float(value)) for value in booster.predict(validation_matrix)]


def select_backtest_candidate(
    baseline: BacktestVariantResult, candidate: BacktestVariantResult, fold_count: int,
) -> tuple[bool, str]:
    mae_gain = (baseline.metrics.mae - candidate.metrics.mae) * 100 / baseline.metrics.mae
    rmse_gain = (baseline.metrics.rmse - candidate.metrics.rmse) * 100 / baseline.metrics.rmse
    stable_wins = candidate.fold_wins >= ceil(fold_count * 2 / 3)
    clear = mae_gain >= 5.0 and rmse_gain >= 5.0 and candidate.metrics.mape <= baseline.metrics.mape and stable_wins
    if clear:
        return True, "Clear improvement across MAE, RMSE, MAPE, and at least two-thirds of chronological folds."
    return False, "Improvement is too small, incomplete across metrics, or unstable across chronological folds."


def run_external_signal_backtest(
    features: list[FeatureRow], store: ExternalSignalStore, fold_count: int = 6,
) -> ExternalSignalBacktestReport:
    validation_months = chronological_backtest_months(features, fold_count)
    type_codes, value_codes = category_codes(features)
    actual: list[float] = []
    predictions: dict[str, list[float]] = {variant: [] for variant in MODEL_VARIANTS}
    fold_wins = {variant: 0 for variant in MODEL_VARIANTS}

    for validation_month in validation_months:
        train = [row for row in features if row.month < validation_month]
        validation = [row for row in features if row.month == validation_month]
        if not train or not validation or max(row.month for row in train) >= validation_month:
            raise ValueError("Chronological backtest split is invalid")
        fold_actual = [float(row.target or 0.0) for row in validation]
        fold_baseline = [row.lag_1 for row in validation]
        actual.extend(fold_actual)
        predictions["naive_baseline"].extend(fold_baseline)
        baseline_fold_mae = calculate_metrics(fold_actual, fold_baseline).mae
        for variant in MODEL_VARIANTS[1:]:
            predicted = _predict_fold(train, validation, type_codes, value_codes, store, variant)
            predictions[variant].extend(predicted)
            if calculate_metrics(fold_actual, predicted).mae < baseline_fold_mae:
                fold_wins[variant] += 1

    baseline_metrics = calculate_metrics(actual, predictions["naive_baseline"])
    results = []
    for variant in MODEL_VARIANTS:
        metrics = calculate_metrics(actual, predictions[variant])
        improvement = (baseline_metrics.mae - metrics.mae) * 100 / baseline_metrics.mae
        results.append(BacktestVariantResult(variant, metrics, improvement, fold_wins[variant]))
    best = min(results, key=lambda result: (result.metrics.mae, result.metrics.rmse, result.metrics.mape))
    baseline = results[0]
    replace, reason = select_backtest_candidate(baseline, best, fold_count) if best.variant != baseline.variant else (
        False, "The current naive baseline remains the lowest-error model.",
    )
    return ExternalSignalBacktestReport(
        results=tuple(results), best_model=best.variant,
        best_improvement_pct=best.improvement_vs_current_pct,
        replace_current=replace, reason=reason, validation_months=tuple(validation_months),
    )
