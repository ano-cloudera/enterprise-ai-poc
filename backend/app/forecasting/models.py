from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DimensionType = Literal["total", "region", "product", "channel"]


class MonthlySales(BaseModel):
    model_config = ConfigDict(frozen=True)

    month: date
    sales_amount: float
    region_name: str | None = None
    product_name: str | None = None
    channel_name: str | None = None
    dimension_type: DimensionType | None = None
    dimension_value: str | None = None


class FeatureRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    month: date
    dimension_type: DimensionType
    dimension_value: str
    year: int
    month_number: int
    quarter: int
    month_index: int
    lag_1: float
    lag_2: float
    lag_3: float
    rolling_mean_3: float
    rolling_std_3: float
    target: float | None = None


class EvaluationMetrics(BaseModel):
    mae: float = Field(ge=0)
    rmse: float = Field(ge=0)
    mape: float = Field(ge=0)


class TrainingMetadata(BaseModel):
    model_name: str = "xgboost"
    model_version: str
    trained_at: datetime
    training_start_date: date
    training_end_date: date
    validation_period: date
    training_rows: int
    forecast_horizon: int = 1
    feature_names: list[str]
    baseline_metrics: EvaluationMetrics
    model_metrics: EvaluationMetrics
    selected_model: Literal["naive_baseline", "xgboost"]
    residual_std: float = Field(ge=0)
    dimension_type_codes: dict[str, int]
    dimension_value_codes: dict[str, int]


class ForecastRow(BaseModel):
    forecast_date: date
    generated_at: datetime
    forecast_horizon: int = 1
    forecast_sales: float = Field(ge=0)
    lower_bound: float = Field(ge=0)
    upper_bound: float = Field(ge=0)
    model_name: str
    model_version: str
    training_cutoff_date: date
    dimension_type: DimensionType
    dimension_value: str


class ForecastLookupResult(BaseModel):
    status: Literal["ok", "FORECAST_NOT_AVAILABLE"]
    requested_period: date
    latest_forecast_period: date | None = None
    latest_actual_period: date | None = None
    rows: list[ForecastRow] = Field(default_factory=list)
