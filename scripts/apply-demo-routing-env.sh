#!/usr/bin/env bash
# P0 demo defaults: auto routing, OSSIE+v3 sidecar (not force-all-v3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

touch "$ENV_FILE"

set_kv() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    if [[ "$(uname)" == Darwin ]]; then
      sed -i '' "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    else
      sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    fi
  else
    printf '\n%s=%s\n' "$key" "$val" >>"$ENV_FILE"
  fi
}

set_kv ASK_DATA_ROUTING auto
set_kv LOCAL_AGENT_PRIMARY 0
set_kv LOCAL_AGENT_BASE_URL "${LOCAL_AGENT_BASE_URL:-http://127.0.0.1:9766}"
set_kv JUDGE_ENABLED true
set_kv JUDGE_MAX_ITERATIONS 2

echo "Updated $ENV_FILE:"
grep -E '^(ASK_DATA_ROUTING|LOCAL_AGENT_PRIMARY|LOCAL_AGENT_BASE_URL|JUDGE_)=' "$ENV_FILE" || true
