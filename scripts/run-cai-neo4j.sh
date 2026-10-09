#!/usr/bin/env bash
# Local smoke for Tempo Scan Neo4j Ontology CAI (HTTP sidecar, not Bolt server).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f .env ]; then set -a; source .env; set +a; fi
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"
export PORT="${PORT:-7680}"
exec python neo4j-cai/app_cai_neo4j.py
