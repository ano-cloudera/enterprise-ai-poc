#!/usr/bin/env bash
# Startup for the "Tempo Scan Frontend" Cloudera AI Application (split
# deployment). Builds and starts the Next.js production server bound
# publicly to CDSW_READONLY_PORT. Talks to the separate "Tempo Scan Backend"
# CAI Application over HTTPS via NEXT_PUBLIC_BACKEND_API_URL — never
# same-origin, and never talks to Qwen directly.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

log() { printf '[frontend] %s\n' "$*"; }
fail() { printf '[frontend] FATAL: %s\n' "$*" >&2; exit 1; }

# --- 1. Validate required environment -------------------------------------
[ -n "${NEXT_PUBLIC_BACKEND_API_URL:-}" ] || fail "NEXT_PUBLIC_BACKEND_API_URL is required — set it to the deployed Backend Application's public URL before building."

case "$NEXT_PUBLIC_BACKEND_API_URL" in
  http://*|https://*) ;;
  *) fail "NEXT_PUBLIC_BACKEND_API_URL must start with http:// or https:// (got: $NEXT_PUBLIC_BACKEND_API_URL)" ;;
esac

PUBLIC_PORT="${CDSW_READONLY_PORT:-${PORT:-3000}}"
[ -n "$PUBLIC_PORT" ] || fail "No public port available (CDSW_READONLY_PORT or PORT)"

log "Backend URL: $NEXT_PUBLIC_BACKEND_API_URL"

# --- 2. Build (NEXT_PUBLIC_* is inlined at build time, not read at runtime) -
# Skip rebuilding only if a build already exists and BUILD_SKIP=1 is set
# explicitly by the operator (e.g. re-running after a crash with an
# unchanged backend URL). By default we always build so the backend URL
# baked into the bundle is guaranteed to match this run's configuration.
if [ "${BUILD_SKIP:-0}" != "1" ] || [ ! -d ".next" ]; then
  log "Building production frontend (this bakes NEXT_PUBLIC_BACKEND_API_URL into the bundle)..."
  npm run build || fail "Frontend build failed"
else
  log "BUILD_SKIP=1 and .next already exists — reusing existing build."
fi

# --- 3. Start Next.js production server (public) ---------------------------
log "Starting on 0.0.0.0:$PUBLIC_PORT..."
exec npx next start -H 0.0.0.0 -p "$PUBLIC_PORT"
