#!/usr/bin/env python3
"""Probe every OSSIE Gold source view on Impala (existence + row count)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from validate_tempo_impala_contract import EXPECTED_SOURCES  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.impala_backend import ImpalaBackend, is_impala_configured  # noqa: E402


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    failures: list[str] = []
    warnings: list[str] = []
    results: dict[str, dict] = {}

    if not is_impala_configured(settings):
        print(
            json.dumps(
                {
                    "status": "misconfigured",
                    "reason": "Impala host/auth not configured (check IMPALA_CREDENTIAL_PROFILE + .env block)",
                },
                indent=2,
            )
        )
        return 2

    backend = ImpalaBackend(settings)
    for source in sorted(EXPECTED_SOURCES):
        sql = f"SELECT COUNT(*) AS row_count FROM {source}"
        try:
            rows = backend.query(sql)
            count = int(rows[0]["row_count"]) if rows else -1
            results[source] = {"row_count": count, "ok": True}
            if count <= 0:
                warnings.append(f"{source}: empty (count={count})")
        except Exception as exc:
            results[source] = {"ok": False, "error": str(exc)[:500]}
            failures.append(f"{source}: {exc}")

    payload = {
        "status": "passed" if not failures else "failed",
        "profile": settings.impala_credential_profile,
        "host": settings.impala_host,
        "views_checked": len(EXPECTED_SOURCES),
        "failures": failures,
        "warnings": warnings,
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
