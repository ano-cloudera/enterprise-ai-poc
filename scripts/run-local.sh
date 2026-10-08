#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Preserve profile from the shell (e.g. IMPALA_CREDENTIAL_PROFILE=aws ./scripts/run-local.sh)
# so sourcing .env does not silently override it.
_SAVED_IMPALA_PROFILE="${IMPALA_CREDENTIAL_PROFILE:-}"
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [ -n "$_SAVED_IMPALA_PROFILE" ]; then
  export IMPALA_CREDENTIAL_PROFILE="$_SAVED_IMPALA_PROFILE"
else
  export IMPALA_CREDENTIAL_PROFILE="${IMPALA_CREDENTIAL_PROFILE:-ingram}"
fi
cleanup() { for pid in $(jobs -p); do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
bash scripts/run-api.sh &
API_PID=$!
sleep 2
bash scripts/run-web.sh &
WEB_PID=$!
echo "API: http://127.0.0.1:8000/docs"
echo "Web: http://127.0.0.1:3000"
wait "$API_PID" "$WEB_PID"
