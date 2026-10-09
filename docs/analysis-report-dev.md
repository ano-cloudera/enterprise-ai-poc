# Analysis Workspace (Genie-style panel)

Split chat (left) + **Analysis Workspace** (right) with tabs **Summary | Table | Query**. **Production** uses `frontend/` + `backend/` (merged 9 Oct 2026, commit `a213b52`). **Pilot copies** `frontend-dev/` + `backend-dev/` stay available for isolated iteration.

## Run production (default)

```bash
make dev
```

- Web: http://127.0.0.1:3000  
- API: http://127.0.0.1:8000  

Uses repo `.env` and `backend/` / `frontend/` as today’s governed Ask AI stack. Panel is on by default (`NEXT_PUBLIC_ANALYSIS_REPORT_PANEL`).

## Run pilot stack (optional)

```bash
chmod +x scripts/run-dev-stack.sh
./scripts/run-dev-stack.sh
```

- Web: http://127.0.0.1:3001  
- API: http://127.0.0.1:8001  

`run-dev-stack.sh` forces **`IMPALA_CREDENTIAL_PROFILE=ingram`** (override with `DEV_IMPALA_PROFILE=aws`). Requires a valid Ingram block in repo `.env` and Kerberos (`kinit`) when hitting real Impala.

```bash
export KRB5_CONFIG=backend/runtime/krb5-ingram.conf   # if off-cluster
kinit your-user@IMID.LOCAL
./scripts/run-dev-stack.sh
```

Preflight: `backend/scripts/test_impala_ingram_env.py` with `PYTHONPATH=backend-dev`. Skip with `DEV_SKIP_IMPALA_SMOKE=1` for UI-only work.

**Note:** `backend-test/` (DuckDB exploratory) also binds **8001** — do not run it at the same time as the pilot stack.

## Behaviour

- After a successful governed turn with chart/table, an **artifact card** appears in chat; the workspace opens on desktop (resizable split).
- **Summary**: executive answer, key findings, chart (workspace height +15% vs inline chat), business implications — unified section typography.
- **Table**: rank column, friendly labels, sort, CSV export.
- **Query**: governed SQL (copy, wrap lines), collapsible data note, **Source** list; no execution-meta chips or separate METRIC block.
- Charts remain **FE-rendered** (Recharts); SQL is read-only display of `governed_sql` from the API.

## Flags

| Env | Default | Meaning |
|-----|---------|---------|
| `NEXT_PUBLIC_ANALYSIS_REPORT_PANEL` | `true` | Disable split panel with `false` |
| `NEXT_PUBLIC_LINEAGE_VIEW_URL` | empty | Optional lineage deep-link base for Query tab |
| `NEXT_PUBLIC_REPORT_DOCUMENT_LABEL` | `Analysis Workspace` | Panel header label |

## Related docs

- Operator snapshot: `PROJECT_STATUS.md`
- Full chronology: `PROJECT_STATE.md` (section “Analysis Workspace in production”)
- Reusable FE patterns: `docs/reusable-fe-capabilities.md`
