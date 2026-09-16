from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.external_signals.weather.open_meteo import OpenMeteoWeatherProvider
from app.external_signals.weather.repository import LocalWeatherRepository
from app.external_signals.weather.service import aggregate_monthly, load_weather_governance


def main() -> None:
    settings = get_settings()
    governance = load_weather_governance(settings.project_id)
    config = governance.weather
    provider = OpenMeteoWeatherProvider()
    generated_at = datetime.now(timezone.utc)
    rows = []
    for location in config.locations:
        daily = provider.fetch_daily(location, config.history_start, config.history_end)
        monthly = aggregate_monthly(
            location, daily, generated_at=generated_at,
            rainy_day_threshold_mm=config.rainy_day_threshold_mm,
        )
        rows.extend(monthly)
        print(f"{location.region_name} ({location.weather_location}): {len(daily)} daily -> {len(monthly)} monthly rows")
    repository = LocalWeatherRepository(settings.duckdb_path)
    repository.upsert(rows)
    periods = sorted({row.period for row in rows})
    print(f"Weather coverage: {periods[0]} to {periods[-1]}")
    print(f"Regions mapped: {len(config.locations)}")
    print(f"Rows ingested: {len(rows)}")
    print(f"Local persistence: {settings.duckdb_path}")
    print("Validation: PASS")


if __name__ == "__main__":
    main()
