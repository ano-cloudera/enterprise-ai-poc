from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from functools import lru_cache
from math import sqrt
from pathlib import Path
import re
from typing import Callable, Iterable

import yaml

from app.core.config import get_settings
from app.external_signals.weather.models import (
    DailyWeather,
    MonthlyWeather,
    TempoScanGovernance,
    WeatherAnalysisIntent,
    WeatherAnalysisResult,
    WeatherEvidence,
    WeatherLocation,
)
from app.forecasting.data import load_monthly_sales
from app.semantic.models import SemanticProject


@lru_cache(maxsize=8)
def load_weather_governance(project_id: str = "tempo_scan") -> TempoScanGovernance:
    settings = get_settings()
    path = settings.project_root / project_id / "config.yaml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return TempoScanGovernance.model_validate({
        "synthetic_data_disclaimer": raw.get("synthetic_data_disclaimer", ""),
        "product_master": raw.get("product_master", []),
        "weather": raw.get("external_signals", {}).get("weather", {}),
    })


def aggregate_monthly(
    location: WeatherLocation,
    rows: Iterable[DailyWeather],
    generated_at: datetime | None = None,
    rainy_day_threshold_mm: float = 0.0,
) -> list[MonthlyWeather]:
    groups: dict[date, list[DailyWeather]] = defaultdict(list)
    for row in rows:
        groups[row.observed_date.replace(day=1)].append(row)
    generated = generated_at or datetime.now(timezone.utc)
    result = []
    for period, daily in sorted(groups.items()):
        count = len(daily)
        result.append(MonthlyWeather(
            period=period,
            region_name=location.region_name,
            weather_location=location.weather_location,
            avg_temperature_c=sum(row.average_temperature_c for row in daily) / count,
            total_precipitation_mm=sum(row.total_precipitation_mm for row in daily),
            avg_relative_humidity_pct=sum(row.average_relative_humidity_pct for row in daily) / count,
            rainy_days=sum(row.total_precipitation_mm > rainy_day_threshold_mm for row in daily),
            generated_at=generated,
        ))
    return result


def _previous_month(period: date) -> date:
    return date(period.year - (period.month == 1), 12 if period.month == 1 else period.month - 1, 1)


def _contains(text: str, value: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(value.lower())}(?!\w)", text) is not None


def resolve_weather_intent(
    question: str,
    dashboard_state: dict,
    project: SemanticProject,
    governance: TempoScanGovernance,
) -> WeatherAnalysisIntent:
    lowered = question.lower()
    region = next((item.region_name for item in governance.weather.locations if _contains(lowered, item.region_name)), None)
    if region is None:
        filters = dashboard_state.get("filters") or {}
        candidate = (filters.get("region") or [None])[0]
        allowed = {item.region_name for item in governance.weather.locations}
        region = candidate if candidate in allowed else None
    current = project.resolution.period_ranges.get("current_month")
    period = date.fromisoformat(current.start) if current else governance.weather.history_end.replace(day=1)
    for key, aliases in project.resolution.periods.items():
        if any(_contains(lowered, alias) for alias in aliases):
            configured = project.resolution.period_ranges.get(key)
            if configured:
                period = date.fromisoformat(configured.start)
                break
    if any(term in lowered for term in ("temperatur", "temperature", "suhu")):
        metric = "temperature"
    elif any(term in lowered for term in ("humidity", "kelembapan")):
        metric = "humidity"
    elif any(term in lowered for term in ("rainy day", "rainy days", "hari hujan")):
        metric = "rainy_days"
    else:
        metric = "precipitation"
    correlation = any(term in lowered for term in ("korelasi", "berkorelasi", "hubungan", "correlation", "dibandingkan", "tren"))
    return WeatherAnalysisIntent(region_name=region, period=period, metric=metric, correlation=correlation)


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return None if denominator == 0 else numerator / denominator


class WeatherAnalysisService:
    def __init__(self, repository, sales_loader: Callable = load_monthly_sales) -> None:
        self.repository = repository
        self.sales_loader = sales_loader

    @staticmethod
    def _metric(row: MonthlyWeather, metric: str) -> float:
        return float({
            "precipitation": row.total_precipitation_mm,
            "temperature": row.avg_temperature_c,
            "humidity": row.avg_relative_humidity_pct,
            "rainy_days": row.rainy_days,
        }[metric])

    def analyze(self, intent: WeatherAnalysisIntent) -> WeatherAnalysisResult:
        sales: dict[tuple[str, date], float] = defaultdict(float)
        for row in self.sales_loader():
            if row.region_name:
                sales[(row.region_name, row.month)] += row.sales_amount
        regions = [intent.region_name] if intent.region_name else sorted({region for region, _ in sales})
        previous = _previous_month(intent.period)
        evidence: list[WeatherEvidence] = []
        sales_context = []
        insufficient = False
        for region in regions:
            current_sales, previous_sales = sales.get((region, intent.period), 0.0), sales.get((region, previous), 0.0)
            sales_context.append({
                "region_name": region, "period": intent.period.isoformat(), "sales": current_sales,
                "comparison_period": previous.isoformat(), "previous_sales": previous_sales,
            })
            weather = self.repository.find(region, date(1900, 1, 1), intent.period)
            by_period = {row.period: row for row in weather}
            if intent.period not in by_period or previous not in by_period:
                continue
            current_weather, previous_weather = by_period[intent.period], by_period[previous]
            aligned = [(sales[(region, row.period)], self._metric(row, intent.metric)) for row in weather if (region, row.period) in sales]
            coefficient = _correlation([item[0] for item in aligned], [item[1] for item in aligned]) if intent.correlation else None
            if intent.correlation and coefficient is None:
                insufficient = True
            weather_current = self._metric(current_weather, intent.metric)
            weather_previous = self._metric(previous_weather, intent.metric)
            evidence.append(WeatherEvidence(
                region_name=region, period=intent.period, comparison_period=previous,
                sales_current=current_sales, sales_previous=previous_sales,
                sales_change=current_sales - previous_sales,
                sales_change_pct=None if previous_sales == 0 else (current_sales / previous_sales - 1) * 100,
                weather_metric=intent.metric, weather_current=weather_current,
                weather_previous=weather_previous, weather_change=weather_current - weather_previous,
                correlation=coefficient, observation_count=len(aligned), source=current_weather.source,
                weather_location=current_weather.weather_location,
            ))
        if not evidence:
            status = "EXTERNAL_SIGNAL_NOT_AVAILABLE"
        elif insufficient:
            status = "INSUFFICIENT_OBSERVATIONS"
        else:
            status = "ok"
        return WeatherAnalysisResult(
            status=status, requested_region=intent.region_name, requested_period=intent.period,
            metric=intent.metric, evidence=evidence, sales_context=sales_context,
        )
