#!/usr/bin/env bash
# Ingram / Impala: validate Gold views then run PDF-session 10Q UAT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BE="$ROOT/backend"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROVIDER="${PROVIDER:-gemini}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi

PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

echo "=== 1/3 OSSIE contract (local) ==="
"$PY" "$ROOT/scripts/validate_tempo_impala_contract.py" || true

echo ""
echo "=== 2/3 Ingram Gold views (Impala) ==="
"$PY" "$ROOT/scripts/validate_ingram_gold_views.py"

echo ""
echo "=== 3/3 PDF session UAT (dry-run + live) ==="
cd "$BE"
export PYTHONPATH="$BE:${PYTHONPATH:-}"
"$PY" scripts/run_pdf_session_uat.py
"$PY" scripts/run_pdf_session_uat.py --live "$BASE_URL" "$PROVIDER"
