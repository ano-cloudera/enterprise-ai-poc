# Trino / CDW Demo Data Bootstrap

Milestone 5.5 provides an explicit write-capable bootstrap path while keeping the FastAPI runtime and `TrinoBackend` read-only.

The controlled workflow is:

```text
Synthetic Tempo data
  -> dedicated bootstrap/load script
  -> governed Trino/CDW catalog and schema
  -> validation with a loader identity
  -> application runtime with a separate SELECT-only identity
```

The data-loader credential may receive narrowly scoped `CREATE SCHEMA`, `CREATE TABLE`, `DELETE`, and `INSERT` permissions for the two approved PoC tables. The application credential must remain separate and `SELECT`-only. Loader credentials are loaded only by `backend/app/bootstrap/` and the two operator scripts; runtime `Settings`, `QueryService`, API routes, LangGraph, and `TrinoBackend` cannot read them.

## Target tables

- `commercial_sales_daily`: 25,480 deterministic rows at date/product/outlet/channel/segment/region grain.
- `commercial_inventory_daily`: 6,370 deterministic rows at date/product/outlet/region grain.

The loader uses the committed Tempo CSV fixtures generated with seed 42. It preserves the Jawa Barat March decline, Modern Trade follow-up, Bodrex Flu & Batuk negative contribution, and three-month trend. Types are intentionally simple: `DATE`, `VARCHAR`, `BIGINT`, and `DOUBLE`. `stockout_flag` remains `BIGINT` because current governed SQL compares it with `0`/`1`.

## Idempotency and write scope

The selected strategy is:

```text
CREATE SCHEMA IF NOT EXISTS
CREATE TABLE IF NOT EXISTS
DELETE FROM each approved PoC table
bounded multi-row INSERT batches
fixed post-load validation
```

Only the configured catalog/schema and the two exact table names are accepted. No arbitrary SQL input exists. This assumes the selected CDW connector supports scoped `DELETE`; rerunning the command repairs a partially loaded run by clearing only these two tables. The operation is not transactional across both tables because the Python Trino client does not provide a cross-statement bootstrap transaction.

## Configuration

Use only `TRINO_LOADER_*` variables for bootstrap and validation:

```env
TRINO_LOADER_JDBC_URL=jdbc:trino://ano03-trino-demo.dw-ano03-cdp-env.a465-9q4k.cloudera.site:443
TRINO_LOADER_CATALOG=<catalog>
TRINO_LOADER_SCHEMA=<schema>
TRINO_LOADER_USER=<loader-user>
TRINO_LOADER_PASSWORD=<loader-secret>
# Or TRINO_LOADER_ACCESS_TOKEN=<loader-token>, never both.
TRINO_LOADER_BATCH_SIZE=500
```

For runtime, use separate `TRINO_*` variables and a SELECT-only identity. Loader settings never fall back to application settings.

## Operator workflow

```bash
.venv/bin/python scripts/generate_sample_data.py
.venv/bin/python scripts/bootstrap_trino_demo.py --dry-run
.venv/bin/python scripts/bootstrap_trino_demo.py
.venv/bin/python scripts/validate_trino_demo_data.py
DATA_BACKEND=trino make dev
```

The dry run validates target scope and prints row counts and planned operations without opening a connection. Bootstrap validates table shape, required-field nulls, dates, business dimensions, hero metrics, and trend availability. The standalone validator additionally compares the five golden scenarios between DuckDB and Trino using numeric tolerance.

Before loading, the operator must choose the real CDW catalog/schema and confirm connector support and permissions. No catalog, schema, or credential is guessed by the generic core.
