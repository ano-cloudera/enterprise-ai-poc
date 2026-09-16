from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.forecasting.data import load_monthly_sales, supported_series
from app.forecasting.external_backtest import load_external_signal_store, run_external_signal_backtest
from app.forecasting.features import build_training_features


def main() -> int:
    features = build_training_features(supported_series(load_monthly_sales()))
    store = load_external_signal_store(get_settings().duckdb_path)
    report = run_external_signal_backtest(features, store)
    print("Model Variant | MAE | RMSE | MAPE | Improvement vs Current")
    print("--- | ---: | ---: | ---: | ---:")
    for result in report.results:
        metrics = result.metrics
        print(
            f"{result.variant} | {metrics.mae:.3f} | {metrics.rmse:.3f} | "
            f"{metrics.mape:.3f}% | {result.improvement_vs_current_pct:+.2f}%"
        )
    print(f"Best model: {report.best_model}")
    print(f"Improvement: {report.best_improvement_pct:.2f}%")
    print(f"Replace current forecast: {'YES' if report.replace_current else 'NO'}")
    print(f"Reason: {report.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
