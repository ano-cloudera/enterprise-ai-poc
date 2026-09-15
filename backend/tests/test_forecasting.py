from __future__ import annotations

from datetime import date

import pytest

from app.forecasting.data import load_monthly_sales
from app.forecasting.data import supported_series
from app.forecasting.evaluation import calculate_metrics, select_model
from app.forecasting.features import build_training_features
from app.forecasting.models import MonthlySales
from app.forecasting.training import chronological_split, train_forecast_model


def test_forecast_history_has_24_chronological_months():
    rows = load_monthly_sales()
    months = sorted({row.month for row in rows})
    assert len(months) == 24
    assert months[0] == date(2022, 4, 1)
    assert months[-1] == date(2024, 3, 1)


def test_extended_history_preserves_existing_hero_totals():
    rows = load_monthly_sales()
    current = sum(row.sales_amount for row in rows if row.month == date(2024, 3, 1) and row.region_name == "Jawa Barat")
    previous = sum(row.sales_amount for row in rows if row.month == date(2024, 2, 1) and row.region_name == "Jawa Barat")
    assert current == pytest.approx(75521.278, abs=0.001)
    assert previous == pytest.approx(90575.469, abs=0.001)


def sample_series():
    return [
        MonthlySales(month=date(2023, month, 1), dimension_type="total", dimension_value="ALL", sales_amount=float(month * 10))
        for month in range(1, 7)
    ]


def test_lag_features_use_previous_periods_only():
    features = build_training_features(sample_series())
    april = features[0]
    assert april.target == 40
    assert (april.lag_1, april.lag_2, april.lag_3) == (30, 20, 10)


def test_rolling_features_exclude_current_and_future_values():
    april = build_training_features(sample_series())[0]
    assert april.rolling_mean_3 == pytest.approx(20)
    assert april.rolling_std_3 == pytest.approx(10)


def test_feature_generation_is_deterministic():
    assert build_training_features(sample_series()) == build_training_features(sample_series())


def test_feature_month_is_the_target_month_not_a_future_source():
    features = build_training_features(sample_series())
    assert features[0].month == date(2023, 4, 1)
    assert features[-1].month == date(2023, 6, 1)


def test_evaluation_metrics_are_correct_and_zero_safe():
    metrics = calculate_metrics([0.0, 2.0, 4.0], [1.0, 2.0, 2.0])
    assert metrics.mae == pytest.approx(1.0)
    assert metrics.rmse == pytest.approx((5 / 3) ** 0.5)
    assert metrics.mape == pytest.approx(25.0)  # zero actual excluded


def test_model_selection_uses_lower_mae_then_rmse():
    baseline = calculate_metrics([10, 20], [9, 19])
    model = calculate_metrics([10, 20], [10, 20])
    assert select_model(baseline, model) == "xgboost"
    assert select_model(model, baseline) == "naive_baseline"


def test_chronological_split_holds_out_latest_month_only():
    features = build_training_features(supported_series(load_monthly_sales()))
    train, test = chronological_split(features)
    assert max(row.month for row in train) < min(row.month for row in test)
    assert {row.month for row in test} == {date(2024, 3, 1)}


def test_training_evaluates_baseline_and_xgboost_and_writes_metadata(tmp_path):
    features = build_training_features(supported_series(load_monthly_sales()))
    result = train_forecast_model(features, tmp_path)
    assert result.model_path.exists()
    assert result.metadata_path.exists()
    assert result.metadata.baseline_metrics.mae >= 0
    assert result.metadata.model_metrics.rmse >= 0
    assert result.metadata.selected_model in {"naive_baseline", "xgboost"}
    assert result.metadata.training_end_date == date(2024, 2, 1)
    assert result.metadata.feature_names


def test_training_is_reproducible(tmp_path):
    features = build_training_features(supported_series(load_monthly_sales()))
    first = train_forecast_model(features, tmp_path / "one")
    second = train_forecast_model(features, tmp_path / "two")
    assert first.metadata.baseline_metrics == second.metadata.baseline_metrics
    assert first.metadata.model_metrics == second.metadata.model_metrics
    assert first.metadata.selected_model == second.metadata.selected_model
