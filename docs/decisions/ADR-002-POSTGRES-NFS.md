# ADR-002: PostgreSQL + NFS for Pilot Storage

**Status:** Accepted  
**Date:** 2026-10-13

## Context

Need durable metadata, sessions, prompts, connector config, and document registry without HA complexity.

## Decision

- **PostgreSQL** (single instance, NFS-backed volume): **recommended** control-plane store for CAI pilot (`STATE_STORE=postgres`)
- **SQLite**: local dev default (`STATE_STORE=sqlite`); **must remain supported** when Postgres is unavailable
- **NFS**: document binaries, parsed artifacts, exports; Postgres and Qdrant data dirs on NFS when those services run on CAI

Do **not** store document BLOBs in PostgreSQL.

## Consequences

- Clear separation: Postgres = pointers + state; NFS = bytes
- Single-instance backup strategy (volume snapshots)
- Future path to external HA Postgres and object storage documented, not built

## Alternatives rejected

- All-in SQLite for production — weak concurrency and isolation
- Document bytes in Postgres — poor cost/performance for PDFs
