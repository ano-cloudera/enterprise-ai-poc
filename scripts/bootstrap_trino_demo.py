from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.bootstrap.config import LoaderConfig, LoaderConfigurationError, LoaderSettings
from app.bootstrap.loader import TrinoDemoLoader
from app.bootstrap.tempo_data import load_tempo_fixture_bundle
from app.bootstrap.validation import TrinoValidationClient, collect_validation_snapshot, validate_snapshot


def run(*, dry_run: bool, debug: bool) -> int:
    config = LoaderConfig.from_settings(LoaderSettings())
    if dry_run:
        config = replace(config, dry_run=True)
    try:
        config.validate()
    except LoaderConfigurationError:
        print("Loader configuration incomplete.")
        print("Set only TRINO_LOADER_* endpoint, catalog/schema, identity, and secret variables.")
        return 2

    bundle = load_tempo_fixture_bundle()
    print("Configuration: valid")
    print(f"Target catalog: {config.catalog}")
    print(f"Target schema: {config.schema}")
    print("Target tables: commercial_sales_daily, commercial_inventory_daily")
    print(f"Planned sales rows: {len(bundle.sales_rows)}")
    print(f"Planned inventory rows: {len(bundle.inventory_rows)}")
    print(f"Batch size: {config.batch_size}")
    if config.dry_run:
        report = TrinoDemoLoader(config).bootstrap(bundle, validate=True)
        print("Mode: DRY RUN — no connection and no writes")
        print("Operations: " + ", ".join(report.operations))
        return 0

    try:
        print("Creating schema/tables and clearing only designated PoC tables...")
        print("Loading sales and inventory rows...")
        TrinoDemoLoader(config).bootstrap(bundle, validate=True)
        print("Validating...")
        client = TrinoValidationClient(config)
        try:
            validation = validate_snapshot(
                collect_validation_snapshot(client.query, config.catalog, config.schema),
                bundle,
            )
        finally:
            client.close()
        print(f"Hero scenario: {validation.hero_scenario}")
        print("Bootstrap complete")
        return 0
    except Exception:
        if debug:
            traceback.print_exc()
        else:
            print("Bootstrap failed safely. No credential or driver details were printed.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load deterministic Tempo fixtures through a dedicated Trino loader identity.")
    parser.add_argument("--dry-run", action="store_true", help="Show exact scope and row counts without connecting or writing.")
    parser.add_argument("--debug", action="store_true", help="Print local diagnostics. May contain driver endpoint details.")
    args = parser.parse_args()
    return run(dry_run=args.dry_run, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
