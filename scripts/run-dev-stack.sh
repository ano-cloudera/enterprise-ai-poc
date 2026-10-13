#!/usr/bin/env bash
# Genie-style report panel: frontend-dev + backend-dev (3001 / 8001).
# Defaults to Impala Ingram profile from repo-root .env (### IMPALA CREDENTIALS INGRAM ENV).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

# Dev stack overrides (does not modify .env on disk)
# DEV_DATA_BACKEND=duckdb → local gold sample (no Impala). Default ingram when cluster is up.
export DEV_DATA_BACKEND="${DEV_DATA_BACKEND:-duckdb}"
export IMPALA_CREDENTIAL_PROFILE="${DEV_IMPALA_PROFILE:-ingram}"
export OSSIE_PROJECT_ID="${OSSIE_PROJECT_ID:-tempo_scan_impala}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001}"

if [ -f "$ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

export PYTHONPATH="$ROOT/backend-dev:${PYTHONPATH:-}"

if [ "${DEV_DATA_BACKEND}" = "duckdb" ]; then
  export DATA_BACKEND=duckdb
  # Dev stack always uses backend-dev runtime (ignore repo .env DUCKDB_PATH meant for backend/).
  export DUCKDB_PATH="${DEV_DUCKDB_PATH:-$ROOT/backend-dev/runtime/tempo_gold_local.duckdb}"
  if [ ! -f "$DUCKDB_PATH" ] || [ "${DEV_DUCKDB_RESEED:-0}" = "1" ]; then
    echo "Local governed DuckDB (seed → $DUCKDB_PATH)…"
    PYTHONPATH="$ROOT/backend-dev" python "$ROOT/backend-dev/scripts/seed_local_gold_duckdb.py" "$DUCKDB_PATH"
  else
    echo "Local governed DuckDB (reuse $DUCKDB_PATH; DEV_DUCKDB_RESEED=1 to rebuild)…"
  fi
  echo ""
elif [ "${DEV_SKIP_IMPALA_SMOKE:-0}" != "1" ]; then
  export DATA_BACKEND="${DATA_BACKEND:-impala}"
  echo "Impala preflight (profile=${IMPALA_CREDENTIAL_PROFILE})…"
  if ! IMPALA_CREDENTIAL_PROFILE="$IMPALA_CREDENTIAL_PROFILE" PYTHONPATH="$ROOT/backend-dev" \
    python "$ROOT/backend/scripts/test_impala_ingram_env.py"; then
    echo ""
    echo "Impala preflight failed. Use DEV_DATA_BACKEND=duckdb or DEV_SKIP_IMPALA_SMOKE=1"
    exit 1
  fi
  echo ""
fi

cleanup() {
  for pid in $(jobs -p); do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

if [ ! -d "$ROOT/frontend-dev/node_modules" ]; then
  echo "Installing frontend-dev dependencies…"
  (cd "$ROOT/frontend-dev" && npm install)
fi

uvicorn app.main:app --app-dir backend-dev --host 127.0.0.1 --port 8001 --reload &
sleep 2
(
  cd "$ROOT/frontend-dev"
  export BACKEND_API_URL="${BACKEND_API_URL:-http://127.0.0.1:8001}"
  export PORT=3001
  exec npm run dev -- -p 3001
) &

echo "Dev stack (data=${DEV_DATA_BACKEND:-impala}, panel on :3001)"
echo "  API: http://127.0.0.1:8001/docs"
echo "  Web: http://127.0.0.1:3001"
wait
