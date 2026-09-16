from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.external_signals.weather.models import DailyWeather, WeatherLocation


class WeatherProviderError(RuntimeError):
    pass


class OpenMeteoWeatherProvider:
    source = "open_meteo"
    endpoint = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, client: httpx.Client | None = None, timeout_seconds: float = 30.0) -> None:
        self.client = client or httpx.Client(timeout=timeout_seconds)

    @staticmethod
    def normalize_response(payload: dict[str, Any]) -> list[DailyWeather]:
        daily = payload.get("daily") or {}
        keys = ("time", "temperature_2m_mean", "precipitation_sum", "relative_humidity_2m_mean")
        values = [daily.get(key) for key in keys]
        if any(not isinstance(value, list) for value in values) or len({len(value) for value in values}) != 1:
            raise WeatherProviderError("INVALID_WEATHER_RESPONSE")
        rows: list[DailyWeather] = []
        for observed, temperature, precipitation, humidity in zip(*values):
            if any(value is None for value in (temperature, precipitation, humidity)):
                continue
            rows.append(DailyWeather(
                observed_date=date.fromisoformat(observed),
                average_temperature_c=float(temperature),
                total_precipitation_mm=float(precipitation),
                average_relative_humidity_pct=float(humidity),
            ))
        return rows

    def fetch_daily(self, location: WeatherLocation, start: date, end: date) -> list[DailyWeather]:
        try:
            response = self.client.get(self.endpoint, params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean",
                "timezone": location.timezone,
            })
            response.raise_for_status()
            return self.normalize_response(response.json())
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise WeatherProviderError("WEATHER_PROVIDER_UNAVAILABLE") from exc

