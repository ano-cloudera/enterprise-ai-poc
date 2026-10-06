#!/usr/bin/env bash
# Full local stack: tempo_agent_v3 (judge loop) + backend-v2 (API/proxy) + frontend-v2.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V3="$ROOT/reference/tempo_agent_v3"
BE="$ROOT/backend-v2"
FE="$ROOT/frontend-v2"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM
PIDS=()

# --- Agent v3 (port 9766) ---
_v3_py="$V3/.venv/bin/python"
if [[ ! -x "$_v3_py" ]] || ! "$_v3_py" -c "pass" 2>/dev/null; then
  echo "Creating tempo_agent_v3 venv (use python3.13 if available)..."
  rm -rf "$V3/.venv"
  if command -v python3.13 >/dev/null 2>&1; then
    python3.13 -m venv "$V3/.venv"
  else
    python3 -m venv "$V3/.venv"
  fi
  "$V3/.venv/bin/pip" install -q -r "$V3/requirements.txt"
fi
# shellcheck source=/dev/null
source "$V3/scripts/use_impala_tstenv06_env.sh" 2>/dev/null || true
if [[ -f "$V3/scripts/use_gemini_llm_env.sh" ]]; then
  # shellcheck source=/dev/null
  source "$V3/scripts/use_gemini_llm_env.sh"
fi
export TEMPO_AGENT_V3_PORT="${TEMPO_AGENT_V3_PORT:-9766}"
export TEMPO_AGENT_HOST="${TEMPO_AGENT_HOST:-127.0.0.1}"
export TEMPO_V2_COGNEE="${TEMPO_V2_COGNEE:-0}"
# deep = coordinator + kpi_pipeline subagent (slower, richer). langgraph = direct KPI graph (faster).
export TEMPO_AGENT_V3_ENGINE="${TEMPO_AGENT_V3_ENGINE:-langgraph}"
export LOCAL_AGENT_ENGINE="${LOCAL_AGENT_ENGINE:-${TEMPO_AGENT_V3_ENGINE}}"
export TEMPO_MOCK_MODE="${TEMPO_MOCK_MODE:-0}"
(
  cd "$V3"
  exec "$V3/.venv/bin/python" api/server.py
) &
PIDS+=($!)
echo "Agent v3: http://${TEMPO_AGENT_HOST}:${TEMPO_AGENT_V3_PORT}/health"

# --- Backend v2 (port 8000) — do not reuse PORT= for Next.js (FE uses 3000). ---
BACKEND_PORT="${BACKEND_PORT:-8000}"
export DEFAULT_LLM_PROVIDER="${DEFAULT_LLM_PROVIDER:-gemini}"
export GEMINI_MODEL="${GEMINI_MODEL:-${MODEL_GEMINI:-gemini-3.8-flash}}"
export LOCAL_AGENT_BASE_URL="${LOCAL_AGENT_BASE_URL:-http://127.0.0.1:${TEMPO_AGENT_V3_PORT}}"
# File .env wins over a stale shell export (e.g. LOCAL_AGENT_PRIMARY=1).
if [[ -f "$ROOT/.env" ]]; then
  _v="$(grep -E '^ASK_DATA_ROUTING=' "$ROOT/.env" | tail -1 | cut -d= -f2- || true)"
  [[ -n "$_v" ]] && export ASK_DATA_ROUTING="$_v"
  _v="$(grep -E '^LOCAL_AGENT_PRIMARY=' "$ROOT/.env" | tail -1 | cut -d= -f2- || true)"
  [[ -n "$_v" ]] && export LOCAL_AGENT_PRIMARY="$_v"
fi
export ASK_DATA_ROUTING="${ASK_DATA_ROUTING:-auto}"
export LOCAL_AGENT_PRIMARY="${LOCAL_AGENT_PRIMARY:-0}"
export LOCAL_AGENT_ENGINE="${LOCAL_AGENT_ENGINE:-langgraph}"
export LOCAL_AGENT_TIMEOUT_SECONDS="${LOCAL_AGENT_TIMEOUT_SECONDS:-180}"
export LOCAL_AGENT_MAX_ATTEMPTS="${LOCAL_AGENT_MAX_ATTEMPTS:-1}"
export IMPALA_CREDENTIAL_PROFILE="${IMPALA_CREDENTIAL_PROFILE:-aws}"
(
  cd "$BE"
  export PYTHONPATH="$BE:${PYTHONPATH:-}"
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PY="$ROOT/.venv/bin/python"
  elif [[ -x "$BE/.venv/bin/python" ]]; then PY="$BE/.venv/bin/python"
  else PY=python3
  fi
  exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
PIDS+=($!)
echo "Backend v2: http://127.0.0.1:${BACKEND_PORT}/health (ASK_DATA_ROUTING=${ASK_DATA_ROUTING}, LOCAL_AGENT_PRIMARY=${LOCAL_AGENT_PRIMARY})"

sleep 2

# --- Frontend (port 3000) ---
export BACKEND_API_URL="${BACKEND_API_URL:-http://127.0.0.1:${BACKEND_PORT}}"
export NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-$BACKEND_API_URL}"
export NEXT_PUBLIC_AGENT_CHIP="${NEXT_PUBLIC_AGENT_CHIP:-Governed · tempo-agent-v3 + Impala}"
export NEXT_PUBLIC_CHAT_STREAM_TIMEOUT_MS="${NEXT_PUBLIC_CHAT_STREAM_TIMEOUT_MS:-120000}"
(
  cd "$FE"
  PORT=3000 exec ./start.sh
) &
PIDS+=($!)
echo "Frontend: http://127.0.0.1:3000"
echo "Press Ctrl+C to stop all services."

wait
