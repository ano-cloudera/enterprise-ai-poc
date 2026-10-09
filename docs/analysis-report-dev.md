# Analysis report panel (frontend-dev / backend-dev)

Experimental **Genie-style** UX: chat on the left, **Analysis document** on the right. Production paths remain `frontend/` and `backend/`.

## Run

```bash
chmod +x scripts/run-dev-stack.sh
./scripts/run-dev-stack.sh
```

- Web: http://127.0.0.1:3001  
- API: http://127.0.0.1:8001  

Uses repo root `.env`. **`run-dev-stack.sh` forces `IMPALA_CREDENTIAL_PROFILE=ingram`** (override with `DEV_IMPALA_PROFILE=aws`). Requires a valid **Ingram** block under `### IMPALA CREDENTIALS INGRAM ENV` and **Kerberos** (`kinit`) for GSSAPI.

```bash
export KRB5_CONFIG=backend/runtime/krb5-ingram.conf   # if off-cluster
kinit your-user@IMID.LOCAL
./scripts/run-dev-stack.sh
```

Preflight runs `backend/scripts/test_impala_ingram_env.py` against `backend-dev` settings. Skip with `DEV_SKIP_IMPALA_SMOKE=1` only for UI-only work.

Point `BACKEND_API_URL` at 8001 if you start processes manually.

## Behaviour

- After a successful governed turn with chart/table, an **artifact card** appears in chat; panel opens on desktop.
- Document sections stack per SUCCESS turn; pills switch section when multiple turns exist.
- **Show governed SQL** appears when `backend-dev` returns `governed_sql` on the chat response.
- Charts are still **FE-rendered** (Recharts) — no Python execution.

## Flags

| Env | Default | Meaning |
|-----|---------|---------|
| `NEXT_PUBLIC_ANALYSIS_REPORT_PANEL` | `true` in frontend-dev | Disable split panel with `false` |

## Merge path

When stable, port `AnalysisReportPanel`, `ReportArtifactCard`, `reportDocument.ts`, and optional `governed_sql` field into `frontend/` and `backend/`.
