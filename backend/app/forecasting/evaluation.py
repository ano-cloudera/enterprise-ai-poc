from __future__ import annotations

import math

from app.forecasting.models import EvaluationMetrics


def calculate_metrics(actual: list[float], predicted: list[float]) -> EvaluationMetrics:
    if not actual or len(actual) != len(predicted):
        raise ValueError("Actual and predicted values must be non-empty and aligned")
    errors = [float(estimate) - float(observed) for observed, estimate in zip(actual, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    percentage_errors = [abs(error / observed) for observed, error in zip(actual, errors) if observed != 0]
    mape = (sum(percentage_errors) / len(percentage_errors) * 100) if percentage_errors else 0.0
    return EvaluationMetrics(mae=mae, rmse=rmse, mape=mape)


def select_model(baseline: EvaluationMetrics, model: EvaluationMetrics) -> str:
    return "xgboost" if (model.mae, model.rmse) < (baseline.mae, baseline.rmse) else "naive_baseline"
