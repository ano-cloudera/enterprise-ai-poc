#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f .env.example ] || { echo ".env.example is required" >&2; exit 1; }
[ -f .env ] || cp .env.example .env
PYTHON_BIN="${PYTHON_BIN:-python3.10}"
command -v "$PYTHON_BIN" >/dev/null || { echo "Python 3.10 is required. Set PYTHON_BIN to a compatible Python 3.10 executable." >&2; exit 1; }
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements-lock.txt
python scripts/generate_sample_data.py
cd frontend
npm install
printf '\nSetup complete. Run: make dev\n'
