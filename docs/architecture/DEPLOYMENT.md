# Deployment — Accelerator (PoC / Pilot)

## Default topology (target)

Single CAI **Backend** application + single CAI **Frontend** application.

| Component | Pilot default | Notes |
|-----------|---------------|--------|
| FastAPI | 1 instance | `app_cai_backend.py` |
| Next.js | 1 instance | `app_cai_frontend.py`, `/api` rewrite |
| PostgreSQL | 1 instance, **data directory on NFS** | M1+ metadata |
| Qdrant | 1 instance, **persistent storage on NFS** | M2+ vectors |
| Document files | NFS mount (`documents/`, `parsed/`, …) | Not in Postgres BLOBs |
| Impala/Trino | **External** customer cluster | Live SQL over network; **not** NFS-backed |

## State store configuration (M1+)

| Variable | Typical value | Notes |
|----------|---------------|--------|
| `STATE_STORE` | `sqlite` | Local development default |
| `STATE_STORE` | `postgres` | **Recommended** for CAI pilot templates |
| `DATABASE_URL` | connection string | Required when `STATE_STORE=postgres` |

Application **must run on SQLite** when Postgres is not configured or unavailable. PostgreSQL is optional per environment, not a hard dependency.

**Redis:** not required. Optional for RQ-backed jobs only.

## Current (M1) deployment

- **Metadata:** `STATE_STORE=sqlite` → SQLite under `backend-dev/runtime/`; `STATE_STORE=postgres` → Alembic + bootstrap seed (fallback to SQLite if Postgres unreachable)
- **Dev data:** DuckDB `tempo_gold_local.duckdb` when `DATA_BACKEND=duckdb`
- **Prod data:** Impala GSSAPI/LDAP per `.env` profiles
- **No** Postgres or Qdrant in repo deployment yet

## Environment categories

1. **Application** — `DATA_BACKEND`, `OSSIE_PROJECT_ID`, routing, LLM keys
2. **Secrets** — Impala Kerberos, API keys (via env today; SecretProvider M1)
3. **Storage paths** — `DUCKDB_PATH`, `USAGE_DB_PATH`, future `NFS_ROOT`
4. **Frontend** — `NEXT_PUBLIC_*`, `BACKEND_API_URL`

## Local dev stacks

| Script | FE | BE |
|--------|----|----|
| `make dev` | :3000 `frontend/` | :8000 `backend/` |
| `scripts/run-dev-stack.sh` | :3001 `frontend-dev/` | :8001 `backend-dev/` |

See also `docs/local-governed-dev.md` (DuckDB governed sample).

## Health

- `GET /health` — liveness
- `GET /health/ready` — LLM + data backend configured

## CAI references

- `docs/cai-deployment.md`
- `docs/cloudera-ai-deployment.md`
- `docs/cai-application-deployment-config.md`

Production HA patterns are **out of scope** for accelerator default; document extension in ADR-002 and ADR-004.
