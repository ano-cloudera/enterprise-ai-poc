#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=backend exec .venv/bin/uvicorn app.mock_market_api.main:app --host 127.0.0.1 --port 8100
