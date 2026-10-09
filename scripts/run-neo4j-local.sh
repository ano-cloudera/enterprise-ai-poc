#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting Neo4j (docker compose)..."
docker compose -f docker-compose.neo4j.yml up -d

echo "Waiting for Neo4j bolt (7687)..."
for _ in $(seq 1 60); do
  if (echo >/dev/tcp/127.0.0.1/7687) 2>/dev/null; then
    break
  fi
  sleep 2
done

export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-tempo-graph-local}"

VENV="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV" ]]; then
  VENV="$ROOT/backend/.venv/bin/python"
fi
if [[ ! -x "$VENV" ]]; then
  echo "Python venv not found. Create .venv and pip install -r backend/requirements.txt" >&2
  exit 1
fi

echo "Seeding domain graph from tempo_domain_graph.yaml..."
cd "$ROOT/backend"
"$VENV" scripts/seed_neo4j_domain_graph.py

echo "Done. Neo4j Browser: http://localhost:7474"
echo "Set in .env: NEO4J_ENABLED=true NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=tempo-graph-local"
