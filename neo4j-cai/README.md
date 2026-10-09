# Tempo Scan Neo4j Ontology (CAI Application)

Sidecar application for **business ontology** (not the main chat backend).

- **Does not** run a Neo4j database inside CAI (use Neo4j Aura, VM, or `docker-compose.neo4j.yml` on a reachable host).
- **Does** optional auto-seed from `backend/knowledge/tempo_domain_graph.yaml` and expose health/catalog HTTP endpoints.

## CAI entrypoint

```
neo4j-cai/app_cai_neo4j.py
```

## Required env (Application settings)

| Variable | Purpose |
|----------|---------|
| `NEO4J_URI` | e.g. `bolt://host:7687` or Aura `neo4j+s://....databases.neo4j.io` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | secret |
| `NEO4J_AUTO_SEED` | `1` to seed on startup |
| `NEO4J_SEED_CLEAR` | `1` to wipe ontology nodes before seed |

## Main Backend app

Point the **Tempo Scan Backend** CAI at the **same** `NEO4J_URI` and set `NEO4J_ENABLED=true`. Chat routing reads intents from Bolt; this app is for ops/seed/health.

## Local

```bash
bash scripts/run-cai-neo4j.sh
curl -s http://127.0.0.1:7680/health/ready
```

See [docs/cloudera-ai-neo4j-application.md](../docs/cloudera-ai-neo4j-application.md).
