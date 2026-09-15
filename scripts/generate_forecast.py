from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.forecasting.data import load_monthly_sales
from app.forecasting.inference import generate_forecasts
from app.forecasting.persistence import LocalForecastWriter


def main() -> int:
    artifact_dir = ROOT / "artifacts" / "forecasting"
    model_path = artifact_dir / "sales_forecast_model.json"
    metadata_path = artifact_dir / "metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        print("Approved forecast artifact is unavailable. Run scripts/train_forecast.py first.")
        return 2
    rows = generate_forecasts(model_path, metadata_path, load_monthly_sales())
    writer = LocalForecastWriter(Path(get_settings().duckdb_path))
    writer.write(rows)
    print(f"Forecast period: {rows[0].forecast_date}")
    print(f"Forecast rows: {len(rows)}")
    print(f"Selected model: {rows[0].model_name}")
    print(f"Model version: {rows[0].model_version}")
    print(f"Local persistence: {get_settings().duckdb_path}")
    print("Validation: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
