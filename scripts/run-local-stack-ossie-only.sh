#!/usr/bin/env bash
# Phase C4: FE + backend only (no tempo_agent_v3 sidecar).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export LOCAL_AGENT_BASE_URL=
export LOCAL_AGENT_PRIMARY=0
export ASK_DATA_ROUTING="${ASK_DATA_ROUTING:-auto}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export PORT=3000
BE="$ROOT/backend"
FE="$ROOT/frontend"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi
export LOCAL_AGENT_BASE_URL=
export LOCAL_AGENT_PRIMARY=0

PIDS=()
cleanup() { for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

(
  cd "$BE"
  export PYTHONPATH="$BE:${PYTHONPATH:-}"
  PY="${ROOT}/.venv/bin/python"
  [[ -x "$PY" ]] || PY=python3
  exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
PIDS+=($!)
echo "Backend v2 (OSSIE only): http://127.0.0.1:${BACKEND_PORT}/health"

sleep 2
export BACKEND_API_URL="http://127.0.0.1:${BACKEND_PORT}"
(
  cd "$FE"
  PORT=3000 exec ./start.sh
) &
PIDS+=($!)
echo "Frontend: http://127.0.0.1:3000"
wait
