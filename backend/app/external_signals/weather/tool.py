from __future__ import annotations

from app.core.config import get_settings
from app.external_signals.weather.models import WeatherAnalysisIntent, WeatherAnalysisResult
from app.external_signals.weather.repository import LocalWeatherRepository
from app.external_signals.weather.service import WeatherAnalysisService


class WeatherAnalysisTool:
    """Deterministic boundary for governed sales/weather evidence."""

    def __init__(self, service: WeatherAnalysisService | None = None) -> None:
        self.service = service or WeatherAnalysisService(LocalWeatherRepository(get_settings().duckdb_path))

    def analyze(self, intent: WeatherAnalysisIntent) -> WeatherAnalysisResult:
        return self.service.analyze(intent)
