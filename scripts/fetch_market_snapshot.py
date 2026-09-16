from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.market_intelligence.calibration import generate_calibrated_market
from app.market_intelligence.collector import MarketSnapshotCollector
from app.market_intelligence.providers.serper import SerperDevMarketProvider
from app.market_intelligence.repository import MarketRepository
from app.market_intelligence.service import load_market_governance


def main() -> None:
    settings = get_settings()
    governance = load_market_governance(settings.project_id)
    repository = MarketRepository(settings.duckdb_path)
    provider = SerperDevMarketProvider(
        api_key=settings.market_collector_api_key, enabled=settings.serper_enabled,
    )
    report = MarketSnapshotCollector(provider, repository, governance).collect(settings.serper_max_queries)
    repository.replace_calibrated(generate_calibrated_market(
        governance, date(2022, 4, 1), date(2024, 3, 1),
        observed_signals=repository.list_latest_snapshots(),
    ))
    print(f"Queries sent: {report.queries_sent}")
    print(f"Normalized results: {report.normalized_results}")
    print(f"Products observed: {', '.join(report.products_observed) or 'none'}")
    print(f"Missing products: {', '.join(report.missing_products) or 'none'}")
    print(f"Failures: {', '.join(report.failures) or 'none'}")
    print(f"Snapshot date: {report.snapshot_at.isoformat()}")
    print(f"Persisted snapshot rows: {repository.snapshot_count()}")


if __name__ == "__main__":
    main()
