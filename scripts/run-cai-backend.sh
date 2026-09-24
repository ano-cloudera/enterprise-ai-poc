#!/usr/bin/env bash
# Startup for the "Tempo Scan Backend" Cloudera AI Application (split
# deployment). Starts the Mock External Market API internally, then the
# FastAPI backend bound publicly to CDSW_READONLY_PORT so the separate
# "Tempo Scan Frontend" CAI Application can reach it over HTTPS.
#
# Does NOT start the Next.js frontend — see scripts/run-cai-frontend.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { printf '[backend] %s\n' "$*"; }
log_market() { printf '[market-api] %s\n' "$*"; }
fail() { printf '[backend] FATAL: %s\n' "$*" >&2; exit 1; }

# --- 1. Validate required environment -------------------------------------
: "${DATA_BACKEND:=duckdb}"
: "${MARKET_API_BASE_URL:=http://127.0.0.1:8100}"
: "${LLM_MODE:=mock}"

if [ "$LLM_MODE" = "remote" ]; then
  [ -n "${QWEN_BASE_URL:-}" ] || fail "QWEN_BASE_URL is required when LLM_MODE=remote (existing Qwen CAI Application URL)"
  [ -n "${QWEN_MODEL:-}" ] || fail "QWEN_MODEL is required when LLM_MODE=remote"
fi

if [ "$DATA_BACKEND" = "duckdb" ]; then
  DUCKDB_PATH="${DUCKDB_PATH:-runtime/tempo_scan.duckdb}"
  [ -f "$DUCKDB_PATH" ] || fail "DuckDB runtime file not found at $DUCKDB_PATH. Run scripts/generate_sample_data.py first, or set DATA_BACKEND=trino with Trino credentials."
fi

PUBLIC_PORT="${CDSW_READONLY_PORT:-${PORT:-8000}}"
[ -n "$PUBLIC_PORT" ] || fail "No public port available (CDSW_READONLY_PORT or PORT)"

if [ -z "${CORS_ORIGINS:-}" ]; then
  log "WARNING: CORS_ORIGINS is not set. Set it to the deployed Frontend Application's public URL once known (see docs/cloudera-ai-deployment.md deployment order)."
fi

# --- 2. Prepare runtime directories ----------------------------------------
mkdir -p runtime

if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"

# --- 1b. Keep the venv in sync with requirements.txt -----------------------
# Reinstalling every start is cheap once deps are cached (pip skips already
# satisfied packages), and it prevents a stale venv from missing a dependency
# that was added to requirements.txt after the venv was first created.
REQ_FILE="$ROOT/backend/requirements.txt"
if [ -f "$REQ_FILE" ]; then
  log "Syncing Python dependencies from backend/requirements.txt..."
  pip install --quiet -r "$REQ_FILE" || fail "pip install -r $REQ_FILE failed"
fi

PIDS=()
cleanup() {
  log "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for_http() {
  local url="$1" label="$2" attempts="${3:-30}"
  for _ in $(seq 1 "$attempts"); do
    if curl -sf -o /dev/null "$url"; then return 0; fi
    sleep 1
  done
  fail "$label did not become healthy at $url"
}

# --- 3. Mock External Market API (internal to this application) -----------
log_market "Starting on 127.0.0.1:8100..."
uvicorn app.mock_market_api.main:app --host 127.0.0.1 --port 8100 >> runtime/market-api.log 2>&1 &
PIDS+=("$!")
wait_for_http "http://127.0.0.1:8100/health" "Mock External Market API"
log_market "ready"

# --- 4. FastAPI backend (public — this is its own CAI Application) --------
log "Starting on 0.0.0.0:$PUBLIC_PORT..."
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "$PUBLIC_PORT" >> runtime/backend-api.log 2>&1 &
PIDS+=("$!")
wait_for_http "http://127.0.0.1:$PUBLIC_PORT/api/health" "Backend API"
log "ready"

log ""
log "Tempo Scan Commercial Intelligence — Backend"
log "Backend API: ready (public port $PUBLIC_PORT)"
log "Market API: ready (internal 127.0.0.1:8100)"
log "Data backend: $DATA_BACKEND"
log "LLM provider: $([ "$LLM_MODE" = "remote" ] && echo "configured (remote Qwen)" || echo mock)"
log ""

wait
