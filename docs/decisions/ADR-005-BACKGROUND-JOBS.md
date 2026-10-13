# ADR-005: Background Job Approach (Pilot)

**Status:** Accepted (M0 revision)  
**Date:** 2026-10-13

## Context

Document parse, embedding, connector sync are asynchronous and may exceed HTTP timeouts.

## Options

| Option | Pros | Cons |
|--------|------|------|
| FastAPI BackgroundTasks | Zero infra | Lost on process restart |
| RQ + Redis | Simple, retries | Needs Redis on CAI |
| Dramatiq | Robust | Extra broker |
| Celery | Feature-rich | Heavy for pilot |

## Recommendation

1. **M2 start:** FastAPI BackgroundTasks + job status rows in Postgres for pilot demos
2. **Upgrade trigger:** If jobs > 2 min or restarts lose work → **RQ** with Redis when available on CAI

## Decision

For **accelerator / pilot (M2+ document jobs):**

1. **Default:** FastAPI **BackgroundTasks** + Postgres job/document status rows.
2. **Optional:** **RQ** **only when Redis is available** in the target CAI environment and operators enable it.

**Redis is not a required accelerator dependency.** Minimum pilot topology has no Redis.

Do not adopt Celery/Dramatiq for the accelerator default.

See [ADR-008](ADR-008-STATE-STORE-AND-REDIS.md).
