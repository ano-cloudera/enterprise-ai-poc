from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import pstdev

import xgboost as xgb

from app.forecasting.evaluation import calculate_metrics, select_model
from app.forecasting.models import FeatureRow, TrainingMetadata


FEATURE_NAMES = [
    "year",
    "month_number",
    "quarter",
    "month_index",
    "lag_1",
    "lag_2",
    "lag_3",
    "rolling_mean_3",
    "rolling_std_3",
    "dimension_type_code",
    "dimension_value_code",
]


@dataclass(frozen=True)
class TrainingResult:
    metadata: TrainingMetadata
    model_path: Path
    metadata_path: Path


def chronological_split(features: list[FeatureRow]) -> tuple[list[FeatureRow], list[FeatureRow]]:
    if len({row.month for row in features}) < 2:
        raise ValueError("At least two feature-complete months are required")
    validation_month = max(row.month for row in features)
    return [row for row in features if row.month < validation_month], [row for row in features if row.month == validation_month]


def category_codes(features: list[FeatureRow]) -> tuple[dict[str, int], dict[str, int]]:
    types = {value: index for index, value in enumerate(sorted({row.dimension_type for row in features}))}
    values = {value: index for index, value in enumerate(sorted({row.dimension_value for row in features}))}
    return types, values


def feature_matrix(features: list[FeatureRow], type_codes: dict[str, int], value_codes: dict[str, int]) -> list[list[float]]:
    return [
        [
            float(row.year), float(row.month_number), float(row.quarter), float(row.month_index),
            row.lag_1, row.lag_2, row.lag_3, row.rolling_mean_3, row.rolling_std_3,
            float(type_codes[row.dimension_type]), float(value_codes[row.dimension_value]),
        ]
        for row in features
    ]


def train_forecast_model(features: list[FeatureRow], artifact_dir: Path) -> TrainingResult:
    train, validation = chronological_split(features)
    type_codes, value_codes = category_codes(features)
    train_matrix = xgb.DMatrix(
        feature_matrix(train, type_codes, value_codes),
        label=[row.target for row in train],
        feature_names=FEATURE_NAMES,
    )
    validation_matrix = xgb.DMatrix(
        feature_matrix(validation, type_codes, value_codes),
        label=[row.target for row in validation],
        feature_names=FEATURE_NAMES,
    )
    booster = xgb.train(
        {
            "objective": "reg:squarederror",
            "tree_method": "hist",
            "max_depth": 3,
            "eta": 0.05,
            "subsample": 1.0,
            "colsample_bytree": 1.0,
            "seed": 42,
            "nthread": 1,
        },
        train_matrix,
        num_boost_round=120,
    )
    actual = [float(row.target or 0) for row in validation]
    baseline_predictions = [row.lag_1 for row in validation]
    model_predictions = [max(0.0, float(value)) for value in booster.predict(validation_matrix)]
    baseline_metrics = calculate_metrics(actual, baseline_predictions)
    model_metrics = calculate_metrics(actual, model_predictions)
    selected = select_model(baseline_metrics, model_metrics)
    selected_predictions = model_predictions if selected == "xgboost" else baseline_predictions
    residuals = [observed - predicted for observed, predicted in zip(actual, selected_predictions)]
    identity = json.dumps(
        {
            "cutoff": max(row.month for row in train).isoformat(),
            "validation": validation[0].month.isoformat(),
            "features": FEATURE_NAMES,
            "selected": selected,
        },
        sort_keys=True,
    ).encode()
    version = hashlib.sha256(identity).hexdigest()[:12]
    metadata = TrainingMetadata(
        model_version=version,
        trained_at=datetime.now(timezone.utc),
        training_start_date=min(row.month for row in train),
        training_end_date=max(row.month for row in train),
        validation_period=validation[0].month,
        training_rows=len(train),
        feature_names=FEATURE_NAMES,
        baseline_metrics=baseline_metrics,
        model_metrics=model_metrics,
        selected_model=selected,
        residual_std=pstdev(residuals) if len(residuals) > 1 else abs(residuals[0]),
        dimension_type_codes=type_codes,
        dimension_value_codes=value_codes,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "sales_forecast_model.json"
    metadata_path = artifact_dir / "metadata.json"
    booster.save_model(model_path)
    metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return TrainingResult(metadata, model_path, metadata_path)
