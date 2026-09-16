#!/usr/bin/env bash
# LEGACY / single-app local validation path (Milestone 7).
#
# The approved Cloudera AI deployment architecture (Milestone 7.2) is now
# THREE separate applications: Tempo Scan Frontend + Tempo Scan Backend +
# the existing Qwen/vLLM application. Use scripts/run-cai-backend.sh and
# scripts/run-cai-frontend.sh for that deployment — see
# docs/cloudera-ai-deployment.md.
#
# This script remains useful for quick local all-in-one testing (one
# process group, one port, same-origin /api/* proxy) but is NOT the path
# used to deploy to real Cloudera AI Applications anymore.
#
# Starts, in order: the Mock External Market API (internal, 127.0.0.1:8100),
# the FastAPI backend (internal, 127.0.0.1:8000), and the Next.js frontend
# (public, CDSW_READONLY_PORT). The browser only ever talks to the frontend's
# public port; /api/* is proxied same-origin to the internal backend.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { printf '%s\n' "$*"; }
fail() { printf 'FATAL: %s\n' "$*" >&2; exit 1; }

# --- 1. Validate required environment -------------------------------------
: "${DATA_BACKEND:=duckdb}"
: "${MARKET_API_BASE_URL:=http://127.0.0.1:8100}"
: "${LLM_MODE:=mock}"

if [ "$LLM_MODE" = "remote" ]; then
  [ -n "${QWEN_BASE_URL:-}" ] || fail "QWEN_BASE_URL is required when LLM_MODE=remote"
  [ -n "${QWEN_MODEL:-}" ] || fail "QWEN_MODEL is required when LLM_MODE=remote"
fi

if [ "$DATA_BACKEND" = "duckdb" ]; then
  DUCKDB_PATH="${DUCKDB_PATH:-runtime/tempo_scan.duckdb}"
  [ -f "$DUCKDB_PATH" ] || fail "DuckDB runtime file not found at $DUCKDB_PATH. Run scripts/generate_sample_data.py first, or set DATA_BACKEND=trino with Trino credentials."
fi

PUBLIC_PORT="${CDSW_READONLY_PORT:-${PORT:-3000}}"
[ -n "$PUBLIC_PORT" ] || fail "No public port available (CDSW_READONLY_PORT or PORT)"

# --- 2. Prepare runtime directories ----------------------------------------
mkdir -p runtime

if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"

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

# --- 3. Mock External Market API (internal) --------------------------------
log "Starting Mock External Market API on 127.0.0.1:8100..."
uvicorn app.mock_market_api.main:app --host 127.0.0.1 --port 8100 >> runtime/market-api.log 2>&1 &
PIDS+=("$!")
wait_for_http "http://127.0.0.1:8100/health" "Mock External Market API"
log "Market API: ready"

# --- 4. FastAPI backend (internal) ------------------------------------------
log "Starting FastAPI backend on 127.0.0.1:8000..."
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 >> runtime/backend-api.log 2>&1 &
PIDS+=("$!")
wait_for_http "http://127.0.0.1:8000/api/health" "Backend API"
log "Backend API: ready"

# --- 5. Next.js frontend (public) -------------------------------------------
log "Building frontend..."
(cd frontend && npm run build) || fail "Frontend build failed"

log "Starting frontend on 0.0.0.0:$PUBLIC_PORT..."
export BACKEND_API_URL="http://127.0.0.1:8000"
(cd frontend && exec npx next start -H 0.0.0.0 -p "$PUBLIC_PORT") &
PIDS+=("$!")
wait_for_http "http://127.0.0.1:$PUBLIC_PORT/" "Frontend" 60
log "Frontend: ready"

log ""
log "Tempo Scan Commercial Intelligence"
log "Frontend: ready (public port $PUBLIC_PORT)"
log "Backend API: ready (internal 127.0.0.1:8000)"
log "Market API: ready (internal 127.0.0.1:8100)"
log "Data backend: $DATA_BACKEND"
log "LLM provider: $([ "$LLM_MODE" = "remote" ] && echo configured || echo mock)"
log ""

wait
