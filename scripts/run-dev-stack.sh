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
export IMPALA_CREDENTIAL_PROFILE="${DEV_IMPALA_PROFILE:-ingram}"
export OSSIE_PROJECT_ID="${OSSIE_PROJECT_ID:-tempo_scan_impala}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001}"

if [ -f "$ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

export PYTHONPATH="$ROOT/backend-dev:${PYTHONPATH:-}"

if [ "${DEV_SKIP_IMPALA_SMOKE:-0}" != "1" ]; then
  echo "Impala preflight (profile=${IMPALA_CREDENTIAL_PROFILE})…"
  if ! IMPALA_CREDENTIAL_PROFILE="$IMPALA_CREDENTIAL_PROFILE" PYTHONPATH="$ROOT/backend-dev" \
    python "$ROOT/backend/scripts/test_impala_ingram_env.py"; then
    echo ""
    echo "Impala preflight failed. Fix Kerberos (.env ingram block + kinit) or run with DEV_SKIP_IMPALA_SMOKE=1"
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

echo "Dev stack (report panel + Impala profile=${IMPALA_CREDENTIAL_PROFILE})"
echo "  API: http://127.0.0.1:8001/docs"
echo "  Web: http://127.0.0.1:3001"
wait
