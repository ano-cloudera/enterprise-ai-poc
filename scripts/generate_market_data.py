from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.market_intelligence.calibration import generate_calibrated_market
from app.market_intelligence.repository import MarketRepository
from app.market_intelligence.service import load_market_governance


def main() -> None:
    settings = get_settings()
    governance = load_market_governance(settings.project_id)
    repository = MarketRepository(settings.duckdb_path)
    rows = generate_calibrated_market(
        governance, date(2022, 4, 1), date(2024, 3, 1),
        observed_signals=repository.list_latest_snapshots(),
    )
    repository.replace_calibrated(rows)
    print(f"Market coverage: {min(row.period for row in rows)} to {max(row.period for row in rows)}")
    print(f"Regions: {len({row.region_name for row in rows})}")
    print(f"Categories: {len({row.category for row in rows})}")
    print(f"Rows persisted: {repository.market_count()}")
    print(f"Local persistence: {settings.duckdb_path}")
    print("Source type: synthetic_calibrated")


if __name__ == "__main__":
    main()
