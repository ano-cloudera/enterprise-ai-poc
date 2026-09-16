from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProductMasterEntry(FrozenModel):
    product_id: str
    product_name: str
    product_categories: list[str] = Field(min_length=1)


class WeatherLocation(FrozenModel):
    region_name: str
    weather_location: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = "Asia/Jakarta"


class WeatherGovernance(FrozenModel):
    provider: Literal["open_meteo"] = "open_meteo"
    history_start: date
    history_end: date
    rainy_day_threshold_mm: float = Field(default=0.0, ge=0)
    proxy_disclaimer: str
    locations: list[WeatherLocation] = Field(min_length=1)


class TempoScanGovernance(FrozenModel):
    synthetic_data_disclaimer: str
    product_master: list[ProductMasterEntry] = Field(min_length=1)
    weather: WeatherGovernance


class DailyWeather(FrozenModel):
    observed_date: date
    average_temperature_c: float
    total_precipitation_mm: float = Field(ge=0)
    average_relative_humidity_pct: float = Field(ge=0, le=100)


class MonthlyWeather(FrozenModel):
    period: date
    region_name: str
    weather_location: str
    avg_temperature_c: float
    total_precipitation_mm: float = Field(ge=0)
    avg_relative_humidity_pct: float = Field(ge=0, le=100)
    rainy_days: int = Field(ge=0, le=31)
    source: Literal["open_meteo"] = "open_meteo"
    generated_at: datetime


class WeatherAnalysisIntent(FrozenModel):
    region_name: str | None = None
    period: date
    metric: Literal["precipitation", "temperature", "humidity", "rainy_days"]
    correlation: bool = False


class WeatherEvidence(FrozenModel):
    region_name: str
    period: date
    comparison_period: date
    sales_current: float
    sales_previous: float
    sales_change: float
    sales_change_pct: float | None
    weather_metric: str
    weather_current: float
    weather_previous: float
    weather_change: float
    correlation: float | None = None
    observation_count: int = 0
    source: str = "open_meteo"
    weather_location: str


class WeatherAnalysisResult(FrozenModel):
    status: Literal["ok", "EXTERNAL_SIGNAL_NOT_AVAILABLE", "INSUFFICIENT_OBSERVATIONS"]
    requested_region: str | None
    requested_period: date
    metric: str
    evidence: list[WeatherEvidence] = Field(default_factory=list)
    sales_context: list[dict] = Field(default_factory=list)
