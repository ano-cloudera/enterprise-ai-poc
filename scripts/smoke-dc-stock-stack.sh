#!/usr/bin/env bash
# Smoke: DC stock accumulation + improvement analysis (screenshot prompt).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUESTION='Tampilkan 10 DC dengan penumpukan stok produk yang tertinggi, lalu analisa apakah ada yang bisa kita lakukan untuk memperbaiki situasi tersebut'

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi
export LOCAL_AGENT_BASE_URL=
export LOCAL_AGENT_PRIMARY=0
export ASK_DATA_ROUTING="${ASK_DATA_ROUTING:-auto}"

BE="$ROOT/backend-v2"
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

echo "=== Dry-run routing ==="
cd "$BE"
"$PY" scripts/simulate_management_questions.py --question "$QUESTION"

echo ""
echo "=== Live /chat (timeout 360s) ==="
"$PY" scripts/simulate_management_questions.py --live --question "$QUESTION" --timeout 360 --provider gemini
