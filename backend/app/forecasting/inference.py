from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import xgboost as xgb

from app.forecasting.data import supported_series
from app.forecasting.features import build_prediction_features
from app.forecasting.models import ForecastRow, MonthlySales, TrainingMetadata
from app.forecasting.training import FEATURE_NAMES, feature_matrix


def generate_forecasts(
    model_path: Path,
    metadata_path: Path,
    historical_rows: list[MonthlySales],
    *,
    generated_at: datetime | None = None,
) -> list[ForecastRow]:
    metadata = TrainingMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    features = build_prediction_features(supported_series(historical_rows))
    if metadata.selected_model == "xgboost":
        booster = xgb.Booster()
        booster.load_model(model_path)
        matrix = xgb.DMatrix(
            feature_matrix(features, metadata.dimension_type_codes, metadata.dimension_value_codes),
            feature_names=FEATURE_NAMES,
        )
        predictions = [max(0.0, float(value)) for value in booster.predict(matrix)]
    else:
        predictions = [row.lag_1 for row in features]
    generated = generated_at or datetime.now(timezone.utc)
    margin = 1.96 * metadata.residual_std
    return [
        ForecastRow(
            forecast_date=feature.month,
            generated_at=generated,
            forecast_sales=prediction,
            lower_bound=max(0.0, prediction - margin),
            upper_bound=prediction + margin,
            model_name=metadata.selected_model,
            model_version=metadata.model_version,
            training_cutoff_date=max(row.month for row in historical_rows),
            dimension_type=feature.dimension_type,
            dimension_value=feature.dimension_value,
        )
        for feature, prediction in zip(features, predictions)
    ]
