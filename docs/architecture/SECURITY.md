# Security Baseline — Accelerator / Pilot

## Scope

Appropriate for **PoC, pilot, and customer demo** — not full enterprise IAM.

## SQL / Ask Data

- **Read-only** database role for Impala/Trino connectors
- Validator allows **SELECT / WITH** only (`app/sql/validator.py`)
- Row caps (`SQL_MAX_ROWS`)
- No arbitrary DDL/DML from user questions

## Secrets

**Today:** credentials in repo-root `.env` and labeled Impala blocks; LLM keys in env.

**Target (M1):** `SecretProvider` abstraction:

- `EnvSecretProvider` (pilot)
- Future: encrypted at rest, enterprise vault

**Rule:** Do not store plaintext connector passwords in normal Postgres config rows; store secret **references** or encrypted blobs.

## Isolation

| Layer | Pilot | Production extension |
|-------|-------|----------------------|
| Workspace | Single default workspace | Row-level `workspace_id` |
| Project | OSSIE folder + config | DB project record |
| Files | NFS path prefix per project | Signed URLs / object ACLs |
| Vectors | Qdrant collection per library | + auth filter |

## File access

- Upload size/count limits (align with Studio-style limits when FE exists)
- Scan/parser sandbox — run workers with minimal OS user
- No execution of user-uploaded code

## Audit (target)

`AuditEvent`: connector tests, prompt activations, skill changes, admin actions, failed auth.

Not implemented in M0.

## Network

- CAI gateway terminates TLS
- CORS restricted via `CORS_ORIGINS`
- Local Agent sidecar optional — treat as trusted internal URL only

## LLM data handling

- Customer policy defines whether prompts/results leave cluster
- Usage store retains token counts, not full prompt text (current behavior)
