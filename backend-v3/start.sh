#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PORT="${PORT:-8001}"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python >/dev/null 2>&1; then PYTHON_BIN=python
  elif command -v python3 >/dev/null 2>&1; then PYTHON_BIN=python3
  elif [[ -x "$ROOT/../.venv/bin/python" ]]; then PYTHON_BIN="$ROOT/../.venv/bin/python"
  else echo "No python found. Set PYTHON_BIN or create ../.venv" >&2; exit 127; fi
fi
if [[ ! -f "${DUCKDB_PATH:-runtime/tempo_local.duckdb}" ]]; then
  echo "DuckDB not found — seeding sample silver (9 domains)..."
  "$PYTHON_BIN" scripts/seed_local_silver.py
fi
exec "$PYTHON_BIN" -m uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "$PORT"
