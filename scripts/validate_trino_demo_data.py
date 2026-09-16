from __future__ import annotations

import argparse
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.bootstrap.config import LoaderConfig, LoaderConfigurationError, LoaderSettings
from app.bootstrap.tempo_data import load_tempo_fixture_bundle
from app.bootstrap.validation import TrinoValidationClient, collect_validation_snapshot, run_golden_parity, validate_snapshot
from app.core.config import Settings
from app.db.duckdb_backend import DuckDBBackend
from app.semantic.loader import load_semantic_project


def run(debug: bool) -> int:
    config = LoaderConfig.from_settings(LoaderSettings())
    try:
        config.validate()
    except LoaderConfigurationError:
        print("Loader configuration incomplete.")
        return 2
    bundle = load_tempo_fixture_bundle()
    trino = TrinoValidationClient(config)
    duckdb = DuckDBBackend(Settings(_env_file=None, data_backend="duckdb"))
    try:
        snapshot = collect_validation_snapshot(trino.query, config.catalog, config.schema)
        report = validate_snapshot(snapshot, bundle)

        def execute(dialect: str, sql: str):
            return duckdb.execute(sql).records() if dialect == "duckdb" else trino.query("golden_parity", sql)

        parity = run_golden_parity(execute, load_semantic_project(), catalog=config.catalog, schema=config.schema)
    except Exception:
        if debug:
            traceback.print_exc()
        else:
            print("Validation failed safely. Re-run with --debug for local operator diagnostics.")
        return 1
    finally:
        trino.close()
        duckdb.close()
    print("LIVE TRINO VALIDATION")
    print(f"Sales row count: {report.sales_row_count}")
    print(f"Inventory row count: {report.inventory_row_count}")
    print(f"Date range: {report.min_date} to {report.max_date}")
    print(f"Hero scenario: {report.hero_scenario}")
    for name, result in parity.scenarios.items():
        print(f"Golden parity {name}: {'PASS' if result.ok else 'FAIL'}")
    return 0 if parity.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live Tempo tables and five DuckDB/Trino golden scenarios.")
    parser.add_argument("--debug", action="store_true")
    return run(parser.parse_args().debug)


if __name__ == "__main__":
    sys.exit(main())
