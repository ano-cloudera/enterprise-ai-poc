#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export BACKEND_API_URL="${BACKEND_API_URL:-${NEXT_PUBLIC_BACKEND_URL:-http://127.0.0.1:8000}}"
exec npm run dev -- --port "${PORT:-3000}"
