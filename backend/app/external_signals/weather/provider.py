from __future__ import annotations

from datetime import date
from typing import Protocol

from app.external_signals.weather.models import DailyWeather, WeatherLocation


class HistoricalWeatherProvider(Protocol):
    source: str

    def fetch_daily(self, location: WeatherLocation, start: date, end: date) -> list[DailyWeather]: ...

