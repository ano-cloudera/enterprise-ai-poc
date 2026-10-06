#!/usr/bin/env bash
# Phase C5: live B3 management questions against OSSIE-only backend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BE="$ROOT/backend"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROVIDER="${PROVIDER:-gemini}"
TIMEOUT="${TIMEOUT:-240}"
OUT="${OUT:-$BE/eval/management_live_$(date +%Y%m%d_%H%M%S).json}"

if ! curl -sf "$BASE_URL/health" >/dev/null; then
  echo "Backend not reachable at $BASE_URL — start: bash scripts/run-local-stack-ossie-only.sh" >&2
  exit 1
fi

PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

cd "$BE"
export PYTHONPATH="$BE:${PYTHONPATH:-}"

echo "=== Dry-run routing ==="
"$PY" scripts/simulate_management_questions.py
echo ""
echo "=== Live run (10 questions) ==="
LOG="$(mktemp)"
"$PY" scripts/simulate_management_questions.py \
  --live \
  --base-url "$BASE_URL" \
  --provider "$PROVIDER" \
  --timeout "$TIMEOUT" \
  | tee "$LOG"

awk '/--- Live results ---/{flag=1;next} flag' "$LOG" > "$OUT"
echo ""
echo "Results JSON: $OUT"
rm -f "$LOG"
