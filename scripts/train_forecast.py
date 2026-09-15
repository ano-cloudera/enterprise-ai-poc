from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.forecasting.data import load_monthly_sales, supported_series
from app.forecasting.features import build_training_features
from app.forecasting.training import train_forecast_model


def main() -> int:
    rows = load_monthly_sales()
    months = sorted({row.month for row in rows})
    features = build_training_features(supported_series(rows))
    result = train_forecast_model(features, ROOT / "artifacts" / "forecasting")
    metadata = result.metadata
    print(f"Historical coverage: {len(months)} months ({months[0]} to {months[-1]})")
    print(f"Training cutoff: {metadata.training_end_date}")
    print(f"Validation period: {metadata.validation_period}")
    print(f"Baseline MAE/RMSE/MAPE: {metadata.baseline_metrics.mae:.3f} / {metadata.baseline_metrics.rmse:.3f} / {metadata.baseline_metrics.mape:.3f}%")
    print(f"XGBoost MAE/RMSE/MAPE: {metadata.model_metrics.mae:.3f} / {metadata.model_metrics.rmse:.3f} / {metadata.model_metrics.mape:.3f}%")
    print(f"Selected model: {metadata.selected_model}")
    print(f"Artifact saved: {result.model_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
