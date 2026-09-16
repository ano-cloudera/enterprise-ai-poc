#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"
python -m compileall -q backend/app scripts
pytest -q backend/tests
cd frontend
npm run build
