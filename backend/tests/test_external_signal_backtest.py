from __future__ import annotations

from datetime import date

import pytest

from app.forecasting.data import load_monthly_sales, supported_series
from app.forecasting.external_backtest import (
    MODEL_VARIANTS,
    BacktestVariantResult,
    ExternalSignalStore,
    chronological_backtest_months,
    select_backtest_candidate,
    signal_features,
)
from app.forecasting.features import build_training_features
from app.forecasting.models import EvaluationMetrics


def _metrics(mae: float, rmse: float, mape: float) -> EvaluationMetrics:
    return EvaluationMetrics(mae=mae, rmse=rmse, mape=mape)


def test_backtest_has_only_the_five_governed_variants():
    assert MODEL_VARIANTS == (
        "naive_baseline",
        "xgboost_internal_only",
        "xgboost_weather",
        "xgboost_market",
        "xgboost_weather_market",
    )


def test_rolling_backtest_months_are_chronological():
    features = build_training_features(supported_series(load_monthly_sales()))
    validation_months = chronological_backtest_months(features, fold_count=6)
    assert validation_months == [
        date(2023, 10, 1), date(2023, 11, 1), date(2023, 12, 1),
        date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1),
    ]
    for validation_month in validation_months:
        training = [row for row in features if row.month < validation_month]
        assert training
        assert max(row.month for row in training) < validation_month


def test_external_features_use_only_previous_month_signals():
    row = next(
        row for row in build_training_features(supported_series(load_monthly_sales()))
        if row.month == date(2024, 3, 1) and row.dimension_type == "region" and row.dimension_value == "Jawa Barat"
    )
    store = ExternalSignalStore(
        weather_national={},
        weather_by_region={
            (date(2024, 2, 1), "Jawa Barat"): (1.0, 2.0, 3.0, 4.0),
            (date(2024, 3, 1), "Jawa Barat"): (91.0, 92.0, 93.0, 94.0),
        },
        market_national={}, market_by_region={}, market_by_product={},
    )
    assert signal_features(row, store, use_weather=True, use_market=False) == [1.0, 2.0, 3.0, 4.0]


def test_unmapped_product_uses_lagged_national_market_signal():
    row = next(
        row for row in build_training_features(supported_series(load_monthly_sales()))
        if row.month == date(2024, 3, 1) and row.dimension_type == "product" and row.dimension_value == "Tempra"
    )
    store = ExternalSignalStore(
        weather_national={}, weather_by_region={},
        market_national={date(2024, 2, 1): (5.0, 6.0, 7.0, 8.0)},
        market_by_region={}, market_by_product={},
    )
    assert signal_features(row, store, use_weather=False, use_market=True) == [5.0, 6.0, 7.0, 8.0]


def test_small_or_unstable_improvement_keeps_current_baseline():
    baseline = BacktestVariantResult("naive_baseline", _metrics(100, 120, 10), 0.0, 0)
    small = BacktestVariantResult("xgboost_weather", _metrics(97, 115, 9), 3.0, 6)
    unstable = BacktestVariantResult("xgboost_market", _metrics(90, 105, 8), 10.0, 3)
    assert select_backtest_candidate(baseline, small, fold_count=6)[0] is False
    assert select_backtest_candidate(baseline, unstable, fold_count=6)[0] is False


def test_clear_stable_improvement_can_be_recommended_without_replacing_artifact():
    baseline = BacktestVariantResult("naive_baseline", _metrics(100, 120, 10), 0.0, 0)
    candidate = BacktestVariantResult("xgboost_weather", _metrics(90, 105, 8), 10.0, 5)
    replace, reason = select_backtest_candidate(baseline, candidate, fold_count=6)
    assert replace is True
    assert "clear" in reason.lower()


def test_safe_mape_remains_zero_safe_for_backtest_metrics():
    from app.forecasting.evaluation import calculate_metrics

    metrics = calculate_metrics([0.0, 100.0], [50.0, 90.0])
    assert metrics.mape == pytest.approx(10.0)
