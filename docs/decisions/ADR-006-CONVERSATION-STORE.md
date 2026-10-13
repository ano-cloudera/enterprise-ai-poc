# ADR-006: ConversationStore Abstraction

**Status:** Accepted (M0 revision)  
**Date:** 2026-10-13

## Context

M1 introduces PostgreSQL for metadata while local dev relies on SQLite today (`conversation_history.sqlite`).

## Decision

- All conversation/session persistence goes through a **ConversationStore** interface.
- **M1:** retain **SQLite** implementation as default for local dev.
- **M1:** add **PostgreSQL** implementation behind the same interface.
- **No hard cutover** — config selects store backend; migration scripts optional when operators enable Postgres.

## Consequences

- `ChatService` stays store-agnostic.
- Pilot can run Postgres while developers keep SQLite.
- Normalized `conversation`/`message` tables apply to Postgres; SQLite may keep legacy layout until unified.

## Related

- [DATA_MODEL.md](../backend/DATA_MODEL.md) — ConversationStore section
- [API_CONTRACT.md](../backend/API_CONTRACT.md) — legacy `/chat` routes unchanged
