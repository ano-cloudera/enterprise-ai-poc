# Health and Model Telemetry

`GET /api/health` reports application/data health independently from model-provider state. Remote Qwen is represented as `unknown` when configured and is not aggressively polled, so an inaccessible or authenticated endpoint does not prevent application startup.

Model states are `mock`, `ok`, `unavailable`, `auth_required`, and `unknown`.

Data backend states are `ok`, `unknown`, `unavailable`, `auth_required`, `auth_failed`, `misconfigured`, and `degraded`. Normal `/api/health` does not make a remote Trino request. The explicit manual probe uses only `SELECT 1` and reports a safe state without driver errors or credentials.

Each analytical turn records safe model telemetry inside the existing event metadata: trace ID, provider, model, latency, retry count, success/failure, fallback use, safe HTTP status, structured-validation status, and token counts when supplied. Prompts, results, credentials, authorization headers, and hidden reasoning are not written to telemetry.

Data telemetry records only backend type, catalog, schema, query latency, row count, success, and safe error code. It excludes passwords, tokens, authorization headers, credential-bearing URIs, and unrestricted raw SQL.
