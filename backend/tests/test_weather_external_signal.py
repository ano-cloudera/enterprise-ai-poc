from __future__ import annotations

from datetime import date, datetime, timezone
import csv
from pathlib import Path

import pytest

from app.external_signals.weather.models import DailyWeather, WeatherAnalysisIntent, WeatherLocation
from app.external_signals.weather.open_meteo import OpenMeteoWeatherProvider
from app.external_signals.weather.repository import LocalWeatherRepository
from app.external_signals.weather.service import (
    WeatherAnalysisService,
    aggregate_monthly,
    load_weather_governance,
    resolve_weather_intent,
)
from app.forecasting.data import load_monthly_sales
from app.graph.nodes import weather
from app.semantic.loader import load_semantic_project


def _location(region: str = "Jawa Barat") -> WeatherLocation:
    return WeatherLocation(
        region_name=region,
        weather_location="Bandung",
        latitude=-6.9175,
        longitude=107.6191,
        timezone="Asia/Jakarta",
    )


def _daily(day: int, precipitation: float, temperature: float = 25.0) -> DailyWeather:
    return DailyWeather(
        observed_date=date(2024, 3, day),
        average_temperature_c=temperature,
        total_precipitation_mm=precipitation,
        average_relative_humidity_pct=80.0,
    )


def test_product_master_contains_representative_portfolio_and_categories():
    governance = load_weather_governance("tempo_scan")
    products = {item.product_name: item for item in governance.product_master}
    expected = {
        "Bodrex", "Bodrex Flu & Batuk", "Oskadon", "Bodrexin", "Vidoran",
        "Hemaviton", "Neo Hormoviton", "HealthyWay", "Rheumacyl Oralinu",
        "Wybert Herbal", "Herbalax",
    }
    assert expected <= set(products)
    assert "Analgesic / Cough & Cold" in products["Bodrex Flu & Batuk"].product_categories
    assert "Nutritional" in products["Vidoran"].product_categories
    assert products["Herbalax"].product_categories == ["Herbal"]
    assert governance.synthetic_data_disclaimer


def test_governed_product_master_fixture_matches_validated_project_config():
    path = Path(__file__).resolve().parents[2] / "projects" / "tempo_scan" / "fixtures" / "commercial_product_master.csv"
    with path.open(encoding="utf-8") as handle:
        fixture = {row["product_name"]: row for row in csv.DictReader(handle)}
    governance = load_weather_governance("tempo_scan")
    assert {item.product_name for item in governance.product_master} == set(fixture)
    assert fixture["Bodrex Flu & Batuk"]["product_category"] == "Analgesic / Cough & Cold"


def test_every_synthetic_sales_region_has_a_governed_location():
    governance = load_weather_governance("tempo_scan")
    mapped = {item.region_name for item in governance.weather.locations}
    sales_regions = {row.region_name for row in load_monthly_sales()}
    assert sales_regions == mapped
    assert next(item for item in governance.weather.locations if item.region_name == "Jawa Barat").weather_location == "Bandung"
    assert "proxy" in governance.weather.proxy_disclaimer.lower()


def test_open_meteo_response_is_normalized_without_api_shapes_leaking():
    payload = {
        "daily": {
            "time": ["2024-03-01", "2024-03-02"],
            "temperature_2m_mean": [25.5, 26.5],
            "precipitation_sum": [0.0, 12.4],
            "relative_humidity_2m_mean": [78.0, 86.0],
        }
    }
    rows = OpenMeteoWeatherProvider.normalize_response(payload)
    assert rows == [
        DailyWeather(observed_date=date(2024, 3, 1), average_temperature_c=25.5, total_precipitation_mm=0, average_relative_humidity_pct=78),
        DailyWeather(observed_date=date(2024, 3, 2), average_temperature_c=26.5, total_precipitation_mm=12.4, average_relative_humidity_pct=86),
    ]
    assert not hasattr(rows[0], "daily")


def test_monthly_aggregation_is_deterministic_and_counts_rainy_days():
    generated = datetime(2026, 9, 15, tzinfo=timezone.utc)
    result = aggregate_monthly(_location(), [_daily(1, 0, 24), _daily(2, 2, 26), _daily(3, 5, 28)], generated)
    assert len(result) == 1
    month = result[0]
    assert month.period == date(2024, 3, 1)
    assert month.avg_temperature_c == pytest.approx(26)
    assert month.total_precipitation_mm == pytest.approx(7)
    assert month.avg_relative_humidity_pct == pytest.approx(80)
    assert month.rainy_days == 2
    assert month.source == "open_meteo"


def test_local_weather_persistence_is_idempotent(tmp_path):
    rows = aggregate_monthly(_location(), [_daily(1, 2), _daily(2, 0)])
    repository = LocalWeatherRepository(tmp_path / "weather.duckdb")
    repository.upsert(rows)
    repository.upsert(rows)
    assert repository.count() == 1
    assert repository.find("Jawa Barat", date(2024, 3, 1), date(2024, 3, 1)) == rows


class MemoryWeatherRepository:
    def __init__(self, rows):
        self.rows = rows

    def find(self, region_name, start, end):
        return [row for row in self.rows if row.region_name == region_name and start <= row.period <= end]


def _weather_history(values):
    rows = []
    for month, rain, rainy_days, temperature in values:
        daily = [DailyWeather(observed_date=date(2024, month, 1), average_temperature_c=temperature, total_precipitation_mm=rain, average_relative_humidity_pct=80)]
        row = aggregate_monthly(_location(), daily)[0]
        rows.append(row.model_copy(update={"rainy_days": rainy_days}))
    return rows


def test_missing_weather_returns_controlled_fallback_with_sales_context():
    service = WeatherAnalysisService(MemoryWeatherRepository([]), sales_loader=load_monthly_sales)
    intent = WeatherAnalysisIntent(region_name="Jawa Barat", period=date(2024, 3, 1), metric="precipitation")
    result = service.analyze(intent)
    assert result.status == "EXTERNAL_SIGNAL_NOT_AVAILABLE"
    assert result.requested_region == "Jawa Barat"
    assert result.requested_period == date(2024, 3, 1)
    assert result.sales_context
    assert result.evidence == []


def test_sales_weather_join_calculates_precipitation_and_rainy_day_changes():
    weather_rows = _weather_history([(2, 100, 10, 26), (3, 150, 15, 25)])
    service = WeatherAnalysisService(MemoryWeatherRepository(weather_rows), sales_loader=load_monthly_sales)
    precipitation = service.analyze(WeatherAnalysisIntent(region_name="Jawa Barat", period=date(2024, 3, 1), metric="precipitation"))
    rainy = service.analyze(WeatherAnalysisIntent(region_name="Jawa Barat", period=date(2024, 3, 1), metric="rainy_days"))
    assert precipitation.evidence[0].weather_change == pytest.approx(50)
    assert rainy.evidence[0].weather_change == pytest.approx(5)
    assert precipitation.evidence[0].sales_change_pct == pytest.approx(-16.62, abs=0.02)


def test_correlation_is_calculated_only_with_enough_aligned_observations():
    enough = _weather_history([(1, 50, 5, 27), (2, 100, 10, 26), (3, 150, 15, 25)])
    service = WeatherAnalysisService(MemoryWeatherRepository(enough), sales_loader=load_monthly_sales)
    result = service.analyze(WeatherAnalysisIntent(region_name="Jawa Barat", period=date(2024, 3, 1), metric="precipitation", correlation=True))
    assert result.status == "ok"
    assert result.evidence[0].observation_count == 3
    assert result.evidence[0].correlation is not None

    insufficient = WeatherAnalysisService(MemoryWeatherRepository(enough[:2]), sales_loader=load_monthly_sales).analyze(
        WeatherAnalysisIntent(region_name="Jawa Barat", period=date(2024, 2, 1), metric="precipitation", correlation=True)
    )
    assert insufficient.status == "INSUFFICIENT_OBSERVATIONS"
    assert insufficient.evidence[0].correlation is None


def test_weather_intent_uses_only_governed_region_period_and_metric():
    project = load_semantic_project("tempo_scan")
    governance = load_weather_governance("tempo_scan")
    intent = resolve_weather_intent("Apakah curah hujan Jawa Barat meningkat bulan ini?", {}, project, governance)
    assert intent.region_name == "Jawa Barat"
    assert intent.period == date(2024, 3, 1)
    assert intent.metric == "precipitation"


@pytest.mark.asyncio
async def test_weather_graph_never_lets_qwen_override_evidence_or_claim_causation(monkeypatch):
    rows = _weather_history([(2, 100, 10, 26), (3, 150, 15, 25)])

    class Tool:
        def analyze(self, intent):
            return WeatherAnalysisService(MemoryWeatherRepository(rows), sales_loader=load_monthly_sales).analyze(intent)

    state = await weather(
        {"question": "Apakah penurunan sales Jawa Barat berkorelasi dengan peningkatan curah hujan?", "language": "id"},
        tool=Tool(),
    )
    summary = state["answer"]["summary"].lower()
    assert state["rows"][0]["weather_change"] == 50
    assert "menyebabkan" not in summary
    assert "sebab-akibat" in " ".join(state["answer"]["caveats"]).lower()


def test_project_owns_at_least_eight_weather_golden_questions():
    questions = load_semantic_project("tempo_scan").weather_golden_questions
    assert len(questions) >= 8
    assert {item.metric for item in questions} >= {"precipitation", "temperature", "rainy_days"}


@pytest.mark.parametrize("golden", load_semantic_project("tempo_scan").weather_golden_questions, ids=lambda item: item.id)
def test_weather_golden_questions_resolve_deterministically(golden):
    project = load_semantic_project("tempo_scan")
    governance = load_weather_governance("tempo_scan")
    intent = resolve_weather_intent(golden.question, {}, project, governance)
    assert intent.region_name == golden.region_name
    assert intent.metric == golden.metric
    assert intent.correlation == golden.correlation
    assert intent.period == date.fromisoformat(project.resolution.period_ranges[golden.period].start)
