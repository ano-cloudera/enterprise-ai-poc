# ADR-008: State Store Selection & Redis Optional

**Status:** Accepted  
**Date:** 2026-10-13

## Context

M1 introduces ConversationStore and UsageStore with multiple backends. Pilot deployments may or may not provision PostgreSQL and Redis on CAI.

## Decision

### Persistence (`STATE_STORE`)

| Environment | Recommended setting | Notes |
|-------------|---------------------|--------|
| Local development | `STATE_STORE=sqlite` | Default; no Postgres required |
| CAI pilot | `STATE_STORE=postgres` | **Recommended default** for pilot docs/templates |

- PostgreSQL is **optional and configurable** — not a hard runtime dependency.
- The application **must remain fully functional with SQLite** when PostgreSQL is unavailable or misconfigured (graceful selection or fallback per store factory).
- ConversationStore and UsageStore both honor `STATE_STORE` (or equivalent unified config).

### Redis

- **Redis is NOT a required accelerator dependency.**
- **Default:** FastAPI **BackgroundTasks** for M2 document/sync jobs.
- **RQ** is **optional only** when Redis is available in the target CAI environment and operators opt in.

## Consequences

- CAI deployment templates document `STATE_STORE=postgres` but ship SQLite-capable images/config for dev/smoke.
- No Redis service in minimum pilot topology.
- Health/readiness must not fail solely because Postgres is absent when `STATE_STORE=sqlite`.

## Related

- [ADR-006](ADR-006-CONVERSATION-STORE.md), [ADR-005](ADR-005-BACKGROUND-JOBS.md), [ADR-007](ADR-007-PILOT-DEFAULTS.md)
