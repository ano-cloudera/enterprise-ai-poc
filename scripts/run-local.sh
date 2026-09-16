#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
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
