# Cloudera AI Application Deployment Config

Captured from the live `triano / tempo-project` CAI workspace on 28 Sep 2026,
for replicating this deployment in another Cloudera AI environment when the
DWH/data warehouse is migrated. Covers all 3 CAI Applications currently
running: `Qwen-3-8-27B-AWQ`, `tempo-frontend`, `tempo-backend`.

**Every credential/secret value below is a placeholder.** Nothing here was a
real secret to begin with — set each `<SET_MANUALLY>` from the source
environment's actual CAI Application settings (or the team's secrets vault) at
deploy time, never by copying values into this file. This file is meant to be
safe to commit to git.

---

## 1. Qwen-3-8-27B-AWQ (self-hosted LLM)

**Runtime**

| Setting | Value |
|---|---|
| Editor / Kernel | JupyterLab / Python 3.10 |
| Edition / Version | Standard / 2026.08 |
| Runtime image | `docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.10-standard:2026.08.1-b5` |
| Spark | Disabled |
| GPU | Enabled — Resource group `ano03-gpu-group`, 1x L40S GPU |
| vCPU / Memory | 8 vCPU / 64 GiB |

**Environment variables**

| Variable | Value |
|---|---|
| `CDSW_APP_POLLING_ENDPOINT` | `/` |
| `MODEL_DIR` | `/home/cdsw/models/Qwen3.8-27B-AWQ` (full path — verify exact spelling against the source environment, screenshot truncated it) |
| `VLLM_MAX_MODEL_LEN` | `8192` |
| `VLLM_MAX_NUM_SEQS` | `2` |

**Notes**

- Entrypoint pattern documented in project memory (`cai_application_entrypoint_convention`): Python `app.py`-style, binds `127.0.0.1`, uses `CDSW_APP_PORT` — not a `.sh` launcher, not `0.0.0.0`.
- Serves an OpenAI-compatible `/v1/chat/completions` proxy in front of `vllm serve` — see `testing/model/vllm/{app.py,proxy.py}`.
- The model weights themselves (`MODEL_DIR`) must be present on the target environment's filesystem before this Application can start — this is a separate data-migration step, not just config replication.

---

## 2. tempo-frontend (Next.js)

**Runtime**

| Setting | Value |
|---|---|
| Editor / Kernel | JupyterLab / Python 3.10 |
| Edition / Version | Standard / 2026.08 |
| Runtime image | `docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.10-standard:2026.08.1-b5` |
| Spark | Disabled |
| GPU | Disabled |
| Resource group | `ano03-group` |
| vCPU / Memory | 2 vCPU / 4 GiB |

**Environment variables**

| Variable | Value |
|---|---|
| `CDSW_APP_POLLING_ENDPOINT` | `/` |
| `NEXT_PUBLIC_BACKEND_API_URL` | `<SET_MANUALLY>` — the target environment's `tempo-backend` Application URL (e.g. `https://tempo-backend.<workspace-domain>`) |
| `NEXT_PUBLIC_APP_NAME` | `Commercial Intelligence` |
| `NEXT_PUBLIC_CUSTOMER_NAME` | `Tempo Scan` |

---

## 3. tempo-backend (FastAPI)

**Runtime**

| Setting | Value |
|---|---|
| Edition / Version | Standard / 2026.08 |
| Runtime image | `docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.10-standard:2026.08.1-b5` |
| Spark | Disabled |
| GPU | Disabled |
| Resource group | `ano03-group` |
| vCPU / Memory | 8 vCPU / 16 GiB |

**Environment variables**

| Variable | Value | Notes |
|---|---|---|
| `CDSW_APP_POLLING_ENDPOINT` | `/` | |
| `APP_ENV` | `production` | |
| `DATA_BACKEND` | `impala` | |
| `LLM_MODE` | `remote` | |
| `QWEN_BASE_URL` | `<SET_MANUALLY>` | Target environment's Qwen Application URL, e.g. `https://qwen-38-awq.<workspace-domain>` |
| `QWEN_MODEL` | `<SET_MANUALLY>` — same value as `MODEL_DIR` above | Full path, e.g. `/home/cdsw/models/Qwen3.8-27B-AWQ` |
| `QWEN_API_TOKEN` | `<SET_MANUALLY>` — screenshot showed `dummy` in the source env | Confirm whether the target environment's Qwen proxy actually enforces this or accepts any value |
| `CORS_ORIGINS` | `<SET_MANUALLY>` | Target environment's `tempo-frontend` URL |
| `GUARDRAILS_ENABLED` | `true` | |
| `GUARDRAILS_TOKEN` | `<SET_MANUALLY>` — **do not copy from screenshots/logs, rotate if ever exposed** | Guardrails Hub API token |
| `PROJECT_ID` | `tempo_scan_impala` | |
| `SEMANTIC_EXECUTION_MODE` | `ossie` | |
| `OSSIE_PROJECT_ID` | `tempo_scan_impala` | |
| `IMPALA_HOST` | `<SET_MANUALLY>` | Target environment's Impala coordinator hostname — **do not reuse the source environment's internal hostname**, it will be wrong for a different DWH/cluster |
| `IMPALA_PORT` | `443` | |
| `IMPALA_DATABASE` | `gold` | |
| `IMPALA_AUTH_MECHANISM` | `LDAP` | |
| `IMPALA_USE_SSL` | `true` | |
| `IMPALA_USE_HTTP_TRANSPORT` | `true` | |
| `IMPALA_HTTP_PATH` | `cliservice` | |
| `IMPALA_USER` | `<SET_MANUALLY>` | |
| `IMPALA_PASSWORD` | `<SET_MANUALLY>` | |
| `CHAT_BACKEND` | `agent_studio` | Routes Ask AI through the Agent Studio workflow's REST API instead of the in-process LangGraph path — see `PROJECT_STATE.md`'s Agent Studio sections for what this depends on |
| `AGENT_STUDIO_BASE_URL` | `<SET_MANUALLY>` | Target environment's `Tempo-Scan-Intelligence-Prod` workflow base URL |
| `AGENT_STUDIO_API_KEY` | `<SET_MANUALLY>` | A Cloudera AI API v2 key for the target environment (same kind as `$CDSW_APIV2_KEY` in a Workbench session) |
| `AGENT_STUDIO_POLL_TIMEOUT_SECONDS` | `<SET_MANUALLY>` | Value not fully visible in the source screenshot — check the live Application before copying |
| `AGENT_STUDIO_POLL_INTERVAL_SECONDS` | `<SET_MANUALLY>` | Value not fully visible in the source screenshot — check the live Application before copying |

**Notes**

- With `CHAT_BACKEND=agent_studio`, this Application does not read `backend/app/ossie/registry.py`/`tempo_core.ossie.yaml` itself for Ask AI — it proxies to the Agent Studio workflow, which has its own bundled copy of those files (see the Agent Studio redeploy steps in `PROJECT_STATE.md`). The `PROJECT_ID`/`SEMANTIC_EXECUTION_MODE`/`OSSIE_PROJECT_ID`/`IMPALA_*` variables here still matter for the Dashboard and any direct `/api/semantic/*` calls, which do run in-process.
- `IMPALA_HOST` in particular must be re-pointed, not copied, when the DWH/data warehouse migrates — this is the whole reason this file exists per this request.

---

## 4. Agent Studio workflow (`Tempo-Scan-Intelligence-Prod`)

Not a CAI Application in the same sense as the three above — configured
through the Agent Studio UI, not an Application's Settings page. Not captured
in this session's screenshots. See `projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md`
for the full manual configuration guide (agent Backstories, tool attachments,
delegation rules) needed to rebuild this workflow from scratch in a new
environment. Each of its custom tools
(`projects/tempo_scan_impala/agent_studio_tools/*/`) also takes Impala
credentials as its own User Parameters (not environment variables — Agent
Studio's tool Configure UI has no separate env-var surface) and must be
reconfigured per tool when the DWH migrates, same `IMPALA_HOST` caveat as
above.

---

## 5. Data migration dependency (not yet done)

This file only captures Application *configuration*. Per this request, the
DWH/data warehouse itself is also planned to migrate to the new environment.
That is a separate, larger effort not covered here:

- All Gold semantic views this project depends on (`datasets/audit/*.sql`
  DDL, plus the newer `datasets/gold/*.sql` files from the 28 Sep 2026
  session — Sales/B2B/Service Level customer+sales_office breakdowns, SAT
  Promo) must be re-created against the new Impala/DWH instance.
- `scripts/validate_tempo_impala_contract.py --json` should be re-run against
  the new environment before cutting over, to confirm the same `20 datasets /
  61 metrics / 81 golden questions` contract holds against the migrated data.
- The model weights for Qwen-3-8-27B-AWQ (see §1) must be copied/re-downloaded
  to the new environment's filesystem.
