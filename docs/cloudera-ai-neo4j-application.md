# Cloudera AI — Tempo Scan Neo4j Ontology (Application #3)

Companion to **FE2 (Frontend)** and **BE2 (Backend)**. The browser and Next.js **never** call Neo4j. Only **BE2** uses Bolt for intent routing; this app is for **seed, health, and ops**.

## Architecture on Cloudera AI

```
User → FE2 (Tempo Scan Frontend)
         │  BACKEND_API_URL (server-side)
         ▼
       BE2 (Tempo Scan Backend) ──Bolt──► Neo4j (Aura / VM)
         │
         │  same NEO4J_URI (read intents)
         ▼
       Optional: CAI "Neo4j Ontology" (this app) ──Bolt──► Neo4j
                    HTTP: /health/ready, /admin/seed
```

## Step 0 — Neo4j database (outside CAI)

1. Create **Neo4j Aura** (or VM) in the same network region as CAI.
2. Copy **Connection URI** (use `bolt+s://...` for Aura).
3. Save username / password.

Local dev: `docker compose -f docker-compose.neo4j.yml up -d` → `bolt://localhost:7687`.

---

## Step 1 — Create CAI Application (UI)

| Field | Value |
|--------|--------|
| **Name** | `Tempo Scan Neo4j Ontology` |
| **Description** | Business intent graph seed & health (TEMPO Q4) |
| **Runtime** | Python 3.10 |
| **Entry point** | `neo4j-cai/app_cai_neo4j.py` |
| **Project / Git** | Same repo as FE2/BE2 (branch you deploy) |

### Application environment variables (copy-paste)

```env
NEO4J_URI=bolt+s://YOUR-AURA-ID.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=YOUR_AURA_PASSWORD
NEO4J_AUTO_SEED=1
NEO4J_SEED_CLEAR=1
```

- **First deploy only:** `NEO4J_SEED_CLEAR=1` + `NEO4J_AUTO_SEED=1` loads `backend/knowledge/tempo_domain_graph.yaml`.
- **Later deploys:** set `NEO4J_AUTO_SEED=0` (or `NEO4J_SEED_CLEAR=0`) unless you intentionally refresh ontology.

### Health check

- Path: `/health/ready`
- Expect JSON: `"status": "ready"` and `neo4j.connected: true`

### Optional manual seed (after app is up)

```bash
curl -X POST "https://YOUR-NEO4J-ONTOLOGY-APP-URL/admin/seed?clear=true"
```

---

## Step 2 — BE2 (Backend) — add Neo4j (required for graph routing)

In **Tempo Scan Backend** CAI Application env, **add** (same Bolt target as above):

```env
NEO4J_ENABLED=true
NEO4J_URI=bolt+s://YOUR-AURA-ID.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=YOUR_AURA_PASSWORD
BUSINESS_GRAPH_ENABLED=true
```

Restart BE2. Verify:

```bash
curl -s "https://YOUR-BE2-URL/health/ready" | jq .components.neo4j
```

Expect `"connected": true`.

---

## Step 3 — FE2 (Frontend) — no Neo4j vars

Unchanged. Only ensure:

```env
BACKEND_API_URL=https://YOUR-BE2-PUBLIC-URL
```

(No `NEO4J_*` on Frontend.)

---

## Deployment order (recommended)

1. Neo4j Aura / DB ready  
2. Deploy **Neo4j Ontology** CAI → `/health/ready` OK  
3. Deploy **BE2** with `NEO4J_ENABLED=true` → `neo4j.connected` OK  
4. Deploy **FE2**  
5. Smoke chat (e.g. pareto, DC penumpukan, clarify picking+unloading)

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `neo4j.connected: false` on BE2 | Check URI (`bolt+s` for Aura), password, outbound firewall from CAI to Neo4j |
| Ontology app `not_ready` | Set `NEO4J_URI` + password; Aura IP allowlist if enabled |
| Chat same as before Neo4j | Expected if seed = YAML; change graph in Neo4j + re-seed to see routing diffs |
| FE2 errors | Unrelated to Neo4j; check `BACKEND_API_URL` |

---

## Local smoke

```bash
docker compose -f docker-compose.neo4j.yml up -d
cd backend && ../.venv/bin/python scripts/seed_neo4j_domain_graph.py --clear
bash scripts/run-cai-neo4j.sh
curl -s http://127.0.0.1:7680/health/ready
```

See also [cloudera-ai-deployment.md](cloudera-ai-deployment.md).
