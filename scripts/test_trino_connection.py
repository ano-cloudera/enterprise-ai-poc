from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import monotonic
import traceback


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.db.base import DataBackendError
from app.db.trino_backend import TrinoBackend


def check(debug: bool) -> int:
    backend = TrinoBackend(get_settings())
    config = backend.config
    try:
        config.validate()
    except (DataBackendError, ValueError):
        print("Trino configuration: invalid")
        print("Set an endpoint plus TRINO_CATALOG and TRINO_SCHEMA.")
        return 2

    print("Trino configuration: valid")
    print(f"Endpoint: {config.host}:{config.port}")
    print(f"TLS: {'enabled' if config.http_scheme == 'https' and config.verify_ssl else 'disabled or unverified'}")
    print(f"Authentication: {config.auth_kind}")
    if config.catalog and config.schema:
        print(f"Governed namespace: {config.catalog}.{config.schema}")
    try:
        started = monotonic()
        health = backend.health_check(probe=True)
        latency_ms = round((monotonic() - started) * 1000)
    except Exception:
        if debug:
            traceback.print_exc()
        else:
            print("Connection: unavailable")
        return 1
    finally:
        backend.close()

    if health.status == "ok":
        print("Connection: success")
        print("SELECT 1: success")
        print(f"Latency: {latency_ms} ms")
        return 0
    if health.status in {"auth_required", "auth_failed"}:
        print(f"Connection: authentication {health.status.removeprefix('auth_')}")
    else:
        print(f"Connection: {health.status}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely test Trino configuration and SELECT 1 without printing secrets.")
    parser.add_argument("--debug", action="store_true", help="Print a local traceback for unexpected errors.")
    return check(parser.parse_args().debug)


if __name__ == "__main__":
    sys.exit(main())
