from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from app.external_signals.weather.models import MonthlyWeather


WEATHER_TABLE = "commercial_weather_monthly"


class LocalWeatherRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _create(connection) -> None:
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {WEATHER_TABLE} ("
            "period DATE, region_name VARCHAR, weather_location VARCHAR, avg_temperature_c DOUBLE, "
            "total_precipitation_mm DOUBLE, avg_relative_humidity_pct DOUBLE, rainy_days BIGINT, "
            "source VARCHAR, generated_at TIMESTAMPTZ, PRIMARY KEY (period, region_name, source))"
        )

    def upsert(self, rows: list[MonthlyWeather]) -> None:
        if not rows:
            return
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            connection.executemany(
                f"INSERT OR REPLACE INTO {WEATHER_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(
                    row.period, row.region_name, row.weather_location, row.avg_temperature_c,
                    row.total_precipitation_mm, row.avg_relative_humidity_pct, row.rainy_days,
                    row.source, row.generated_at,
                ) for row in rows],
            )

    def find(self, region_name: str, start: date, end: date) -> list[MonthlyWeather]:
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            records = connection.execute(
                f"SELECT * FROM {WEATHER_TABLE} WHERE region_name = ? AND period BETWEEN ? AND ? ORDER BY period",
                [region_name, start, end],
            ).fetchall()
            columns = [item[0] for item in connection.description]
        return [MonthlyWeather.model_validate(dict(zip(columns, row))) for row in records]

    def count(self) -> int:
        with duckdb.connect(str(self.path)) as connection:
            self._create(connection)
            return int(connection.execute(f"SELECT COUNT(*) FROM {WEATHER_TABLE}").fetchone()[0])

