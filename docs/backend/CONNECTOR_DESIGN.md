# Connector Architecture — Design

## Goals

- Pluggable connectors for **structured** and **unstructured** sources
- Read-only default for SQL connectors
- Secrets via SecretProvider (not plaintext in `config_json`)

## Connector types

| Type (examples) | Mode | Initial priority |
|-----------------|------|------------------|
| `impala` | Live SQL | **P0 — first** (exists as `ImpalaBackend`; primary pilot path) |
| `trino` | Live SQL | **P1 — second** (after Impala adapter is in connector registry) |
| `duckdb_governed` | Live SQL (dev) | P0 local only |
| `slack` | Sync → documents → Qdrant | P2 |
| `gmail` | Sync → documents → Qdrant | P2 |
| *(future)* | Registry-extensible | Added without DB enum migration |

### Connector type registry

- Store `connector.type` as **text** in PostgreSQL.
- Validate against an in-code **registry** mapping `type` → adapter class + config schema.
- New connector types (e.g. `s3_inventory`, `sharepoint`) register adapters; **do not** use a closed Postgres enum.

**Distinction:** Impala/Trino answer Ask Data questions **live**. Slack/Gmail should **not** be queried live per user message in pilot — prefer scheduled sync into knowledge pipeline.

## Interface (conceptual)

```python
class Connector(Protocol):
    def connect(self) -> None: ...
    def test(self) -> ConnectorTestResult: ...
    def metadata(self) -> ConnectorMetadata: ...  # schemas, tables, capabilities
    def search(self, query: ConnectorSearchRequest) -> ConnectorSearchResult: ...  # optional catalog search
    def fetch(self, request: FetchRequest) -> FetchResult: ...  # SQL execution for SQL connectors
    def sync(self, job: SyncJobContext) -> SyncResult: ...  # for slack/gmail
```

Exact method split may refine during M4 — **audit finding:** today `ImpalaBackend.query()` + `DuckDBGovernedBackend` map to `fetch()`.

## SQL connector adapter

Wrap existing:

- `app/db/impala_backend.py`
- `app/db/duckdb_governed_backend.py` (dev-only connector type `duckdb_governed`)

Trino: new adapter implementing same `BackendQueryResult` / telemetry pattern as `app/db/base.py`.

Governed Ask Data continues to use OSSIE SQL generation → validator → connector.fetch(sql).

## Configuration model

Postgres `connector` row + `secret_ref`:

```json
{
  "host": "...",
  "port": 21050,
  "database": "gold",
  "auth_mechanism": "GSSAPI",
  "use_ssl": true,
  "options": {}
}
```

Kerberos keytab paths via secret ref, not inline.

## Sync jobs (Slack/Gmail — future)

```text
Connector.sync()
  → fetch messages/files since cursor
  → normalize to Document records
  → enqueue parse/embed pipeline
  → update connector_sync_job stats
```

## API (target)

- `POST /api/v1/projects/{id}/connectors`
- `POST .../connectors/{id}/test`
- `POST .../connectors/{id}/sync` (async job id)
- `GET .../connectors/{id}/metadata`

## FE (target)

Connectors grid (empty state in CAI Studio screenshots) — **to be built** in `frontend-dev` when M4 lands; not in repo today.

## Health integration

`/health/ready` should report active **default project connector** status instead of hardcoded `impala` key — target `structured_data: ready|degraded`.
