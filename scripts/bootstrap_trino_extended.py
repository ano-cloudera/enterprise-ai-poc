from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.bootstrap.config import LoaderConfig, LoaderConfigurationError, LoaderSettings
from app.bootstrap.loader import ExtendedTrinoLoader
from app.bootstrap.tempo_data import DUCKDB_SOURCED_SPECS, DEFAULT_DUCKDB_PATH, load_tempo_extended_bundle


def run(*, dry_run: bool, debug: bool, duckdb_path: Path) -> int:
    config = LoaderConfig.from_settings(LoaderSettings())
    if dry_run:
        config = replace(config, dry_run=True)
    try:
        config.validate()
    except LoaderConfigurationError:
        print("Loader configuration incomplete.")
        print("Set only TRINO_LOADER_* endpoint, catalog/schema, identity, and secret variables.")
        return 2

    if not duckdb_path.is_file():
        print(f"DuckDB runtime file not found at {duckdb_path}.")
        print("Run the relevant generator first: scripts/train_forecast.py, scripts/fetch_weather_history.py, "
              "scripts/generate_market_data.py, and/or scripts/fetch_market_snapshot.py.")
        return 2

    bundle = load_tempo_extended_bundle(duckdb_path)
    present = sorted(bundle.rows_by_table)
    missing = sorted(spec.name for spec in DUCKDB_SOURCED_SPECS if spec.name not in bundle.rows_by_table)

    print("Configuration: valid")
    print(f"Target catalog: {config.catalog}")
    print(f"Target schema: {config.schema}")
    print(f"Tables present in local runtime: {', '.join(present) or '(none)'}")
    if missing:
        print(f"Tables skipped (not yet generated locally): {', '.join(missing)}")
    for name in present:
        print(f"Planned {name} rows: {len(bundle.rows_by_table[name])}")
    print(f"Batch size: {config.batch_size}")

    if not present:
        print("Nothing to load — no DuckDB-sourced governed table has data in the local runtime.")
        return 0

    if config.dry_run:
        report = ExtendedTrinoLoader(config).bootstrap(bundle, validate=True)
        print("Mode: DRY RUN — no connection and no writes")
        print("Operations: " + ", ".join(report.operations))
        return 0

    try:
        print("Creating schema/tables and clearing only designated extended tables...")
        report = ExtendedTrinoLoader(config).bootstrap(bundle, validate=True)
        print(f"Loaded tables: {', '.join(report.tables)}")
        print("Bootstrap complete")
        return 0
    except Exception:
        if debug:
            traceback.print_exc()
        else:
            print("Bootstrap failed safely. No credential or driver details were printed.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load the DuckDB-sourced governed tables (product master, weather, market intelligence, "
        "market digital snapshot) into Trino/Iceberg through a dedicated Trino loader identity."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show exact scope and row counts without connecting or writing.")
    parser.add_argument("--debug", action="store_true", help="Print local diagnostics. May contain driver endpoint details.")
    parser.add_argument("--duckdb-path", default=str(DEFAULT_DUCKDB_PATH), help="Path to the local governed DuckDB runtime file.")
    args = parser.parse_args()
    return run(dry_run=args.dry_run, debug=args.debug, duckdb_path=Path(args.duckdb_path))


if __name__ == "__main__":
    sys.exit(main())
