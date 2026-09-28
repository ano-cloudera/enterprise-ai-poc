# Tempo Scan Commercial Intelligence — Project State

**Repo**: `enterprise-ai-poc` (github.com/ano-cloudera/enterprise-ai-poc), branch `main`
**Updated**: 28 Sep 2026 — Governed semantic layer expanded to nine domains and committed locally. SAT Promo Gold view is deployed and validated in Workbench. The updated OSSIE runtime has not yet been rebuilt/redeployed to Agent Studio, and the newest local commits have not yet been pushed to `origin/main`.

## Current checkpoint: nine-domain semantic layer (28 Sep 2026)

### Repository state

- Semantic implementation commit: `bc517b7 feat: expand TEMPO semantic layer to nine domains`.
- Previous planning commit: `b4ea934 docs: design full TEMPO metric coverage`.
- `origin/main` is still at `a3bc9fb`; the planning, implementation, and this checkpoint update are local-only and still need an explicit push.
- The semantic expansion commit contains the OSSIE model, resolver/governance changes, business-question catalogs, Gold/audit SQL, Agent Studio instructions, tests, and acceptance evidence.

### Frozen semantic contract

- **9 domains**: Sales/Sell-In, B2B/Sell-Out, Stock Tempo, Stock SAT-IDM, SAT OOS, Service Level, Picking, Unloading, and SAT Promo.
- **15 OSSIE datasets**.
- **50 governed/candidate metrics**.
- **75 golden questions**.
- Contract validator result: `valid=true`, with no validation errors. Metrics marked `pending business confirmation` remain intentional governance warnings, not technical failures.
- Latest verification before commit:
  - Full backend suite: **449 passed**, 2 dependency deprecation warnings.
  - Next.js production build: **PASS**.
  - Focused OSSIE/Agent Studio/Impala suite: **104 passed**.

### Business definitions locked into the model

- Stock SAT-IDM DC Stock and Store Stock are separate analytical levels. They must never be added into a synthetic total-pipeline metric or converted into an unapproved imbalance/ratio KPI.
- Sales and B2B terminology is explicit: `bill_qty`/`bill_val` are billing quantity/value; `do_qty`/`do_amt` are Delivery Order quantity/amount.
- B2B branch and Tempo sales office are separate dimensions and are not aliases.
- SAT OOS represents field-audit availability at the evaluated DC or B2B unit.
- SAT Promo currently supports December 2024 observation counts and distinct-material counts by raw `mekanisme` and raw `program_status`.
- SAT Promo `program_status` values `Y`, `X`, and `T` remain raw/unmapped codes. The workflow must not call them active/inactive/success/failed until Tempo supplies the controlled definition.
- Promo ROI, uplift, cost, attributed revenue, and October-November trend remain intentionally unsupported because the available source does not govern those claims.

### SAT Promo Gold status

Canonical view: `gold.rpt_sat_promo_material_december_semantic`.

- View successfully deployed in Cloudera Workbench using Impala-compatible `DROP VIEW IF EXISTS` + `CREATE VIEW` syntax.
- Semantic rows: **297**.
- Source observations represented: **67,837**, exactly matching the Silver source total.
- Duplicate canonical-grain rows: **0**.
- Negative observation rows: **0**.
- Rows outside December 2024: **0**.
- Null/blank material rows: **0**.
- Evidence: `datasets/qa/23_sat_promo_gold_contract.md`.

### Agent Studio deployment status

The existing production workflow remains live with the earlier latency and stability improvements, but it has **not yet been redeployed with the new nine-domain OSSIE bundle**.

Next actions, in order:

1. Push the local `main` commits to `origin/main` when approved.
2. Pull the updated `main` branch in the Cloudera Workbench checkout.
3. Run `scripts/validate_tempo_impala_contract.py --json` in Workbench and confirm `15 datasets / 50 metrics / 75 golden questions`.
4. Rebuild `workflow_data/enterprise-ai-poc`, redeploy `Tempo-Scan-Intelligence-Prod`, and verify the deployed artifact contains the updated OSSIE model, governance, golden questions, and tool files.
5. Execute the nine-domain UI/API acceptance matrix in `docs/qa/2026-09-28-agent-studio-nine-domain-acceptance.md`, including SAT Promo happy paths and safety controls.
6. Only after the Agent Studio baseline passes, begin the deferred Semantica implementation assessment/PoC. Current work is assessment documentation only (`docs/SEMANTICA_ASSESSMENT.md`); no additional Cloudera AI Application has been created for Semantica.

---

**⚠️ Historical handoff note (earlier on 28 Sep 2026, before the nine-domain expansion)**:

Everything through commit `ea5f5f7` is committed and pushed to `origin/main`. Today's session was almost entirely Agent Studio production debugging + latency optimization, working live against the deployed `Tempo-Scan-Intelligence-Prod` workflow via its REST API (`createSession`/`kickoff`/`events` — see below). Recent history (newest first):

```
ea5f5f7 feat: add execute_governed_metric_query tool to shorten the Data Agent's LLM chain
76c3690 chore: gitignore reference/ - found live-looking credentials in it
bf9e47d fix: follow-up questions to the agent_studio backend had no context
d28e10e refactor: render Agent Studio's Markdown answers verbatim instead of parsing them into a fixed card
758e5ac fix: numbered lists collapsed into one run-on Key Drivers paragraph
5bd7df1 fix: add anti-buffering headers to /chat/stream so progress actually streams
b452391 fix: analysis was disappearing from Ask AI answers, empty drivers/caveats
69d6a13 fix: chatStream() was dropping the terminal done frame on Cloudera AI
7bfdfec fix: send SSE keep-alive heartbeats to survive CAI's proxy idle timeout
02ec1b8 feat: stream Agent Studio progress to Ask AI instead of a static spinner
738901e feat: add Agent Studio chat backend behind CHAT_BACKEND env var flag
```

### What actually got fixed today (in the order they were found)

1. **`CHAT_BACKEND=agent_studio` wired up** (`738901e`) — `backend/app/services/chat.py`'s `run_chat()` now branches on `settings.chat_backend`: `"graph"` (default, unchanged LangGraph path) or `"agent_studio"` (new — calls the deployed Agent Studio workflow's REST API and adapts its Markdown output). Requires 3 new env vars on the `tempo-backend` CAI Application: `CHAT_BACKEND=agent_studio`, `AGENT_STUDIO_BASE_URL` (the workflow's own base URL, e.g. `https://workflow-a9ac1dd9-....cloudera.site`), `AGENT_STUDIO_API_KEY` (a Cloudera AI API v2 key, same as `$CDSW_APIV2_KEY` in a session).
2. **SSE progress streaming** (`02ec1b8`, `7bfdfec`, `69d6a13`, `5bd7df1`) — `POST /api/chat/stream` streams `{"type": "progress", "label": "..."}` frames (translated from raw Agent Studio events into natural Indonesian, e.g. "Mengambil angka dari data governed...") while the multi-agent chain runs, then one final `{"type": "done", "response": ChatResponse}`. Took 3 follow-up fixes to actually work end-to-end against Cloudera AI's own reverse proxy and the browser's `ReadableStream` behavior — see "Non-obvious infra lessons" below.
3. **Markdown rendered verbatim, not parsed into a fixed card** (`b452391`, `758e5ac`, `d28e10e`) — the original design tried to extract `summary`/`drivers`/`caveats` from Agent Studio's Markdown answer by pattern-matching section headings. This kept breaking (exact-heading mismatch, then a numbered-list answer got flattened into one run-on paragraph) because real Analysis Agent answers vary in shape more than a fixed schema can represent. Replaced with `react-markdown` + `remark-gfm` rendering the Markdown directly (`ExecutiveAnswer.markdown` field, `MarkdownAnswer` component in `AskAIPage.tsx`); `markdown_chart_adapter.py` now only extracts the first table for `chart_spec`/`ChartSpec` (Recharts still needs structured data — everything else is untouched raw Markdown).
4. **Follow-up questions lost context** (`bf9e47d`) — `agent_studio_client.stream_workflow()`/`run_workflow()` both accept a `context` param, but nothing was passing one, so every question went to Agent Studio standalone. Fixed by loading the last assistant turn's Markdown from `ConversationStore` and passing it as `context` — the Master Agent's own Backstory already defines a `FOLLOW_UP` envelope for this, it just never received input to build one from.
5. **`execute_governed_metric_query` — new combined Agent Studio tool** (`ea5f5f7`) — biggest latency win. Colleague Irvan's separate Agent Studio workflow (`reference/workflow irvan/`, gitignored — **found live-looking credentials in `demo_config.py`, tell Irvan to rotate them**) uses a single-agent/single-tool/no-delegation design (`crew_ai_allow_delegation: false`) that answers in ~1-2 LLM calls by wrapping an entire resolve→query→execute pipeline in one Python tool call. Adopted that pattern for just the Data Agent's three technical tool calls: `projects/tempo_scan_impala/agent_studio_tools/execute_governed_metric_query/tool.py` runs `resolve_with_llm_fallback` → `get_metric_definition` → `execute_query` (the exact same `TempoOssieService` calls the 3 standalone tools already used) as one Python function instead of three separate LLM-driven ReAct tool calls. Master Agent and Analysis Agent (LLM narration) were deliberately left untouched.

### Agent Studio manual fixes applied today (not in this repo — done directly in the Agent Studio UI, not version-controlled)

- **Registered `execute_governed_metric_query` as a 5th tool on TEMPO Data Agent** (the 3 original tools — `resolve_semantic_object`, `get_metric_definition`, `execute_governed_query` — were kept attached, not removed, as a fallback for edge cases like re-executing with different filters against an already-resolved metric).
- **Added a "Preferred tool" section to TEMPO Data Agent's Backstory** instructing it to call `execute_governed_metric_query` once instead of the three separate tools for standard metric questions.
- **Added a "Response length policy" section to TEMPO Analysis Agent's Backstory** — simple single-metric questions now get a 2-3 sentence answer (still always including `metric_id`/`source_view`/governance caveat) instead of the full Ringkasan/Implikasi Bisnis/Status structure, which is now reserved for genuinely complex questions (breakdowns, trends, ratios, or an explicit request for analysis).
- **Fixed a recurring Master Agent bug**: the Master Agent's Backstory few-shot examples used the coworkers' display **Name** (`"TEMPO Data Agent"`, `"TEMPO Analysis Agent"`) in the `"coworker"` field of every `Ask question to coworker` tool call, but CrewAI matches coworkers by **Role** (`"TEMPO Governed Data Retriever"`, `"TEMPO Business Insight Explainer"`), not Name. This caused the Master Agent to fail its first delegation attempt on nearly every turn and silently self-correct with a retry — wasting one full LLM round-trip every time. Fixed by rewriting every `"coworker"` value in the Backstory's few-shot examples to use the Role string.

**Net result**: a simple single-metric question (e.g. "Berapa Company Fill Rate selama Q4 2024?") now completes in **~20 seconds** (Data Agent ~13s including one fast tool call, Analysis Agent ~7s with the short-form response) — down from the original 3-agent chain's ~9 LLM calls taking 40-60+ seconds. Confirmed via live testing directly in the Agent Studio "Test" tab (Thoughts panel timing), not just theoretical.

### Non-obvious infra lessons from today (useful if this recurs)

- **Cloudera AI's own reverse proxy aborts SSE connections that go quiet** (`net/http: abort Handler` from a Go/gin component, not app code) if no bytes flow for a stretch — fixed with a `: keep-alive\n\n` SSE comment heartbeat every 15s during Agent Studio's polling gaps. Also needed explicit `X-Accel-Buffering: no` / `Cache-Control: no-cache, no-transform` headers, or an intermediate layer buffered the *entire* SSE response before forwarding it (progress looked frozen, then the whole answer appeared at once).
- **Browser `ReadableStream.getReader().read()` can report `done: true` in the same call that delivers the final chunk**, not only in a separate empty final read — a naive `if (done) break` before processing that chunk's buffer silently drops the last SSE frame(s), including the terminal `{"type": "done"}` payload. `frontend/src/lib/api.ts`'s `chatStream()` now always drains the buffer before checking whether to stop.
- **Agent Studio matches `"coworker"` in a delegation tool call by the coworker's Role field, not its Name field** — easy to get backwards when writing few-shot examples by hand (see above).
- **`markdown_chart_adapter.py`'s repeated fragile-parsing failures were symptomatic, not a one-off bug** — every fix (exact heading match → keyword match → per-line exclusion → numbered-list support) fixed one shape of Agent Studio's Markdown output but broke on the next variation. The actual fix was to stop parsing meaning out of free-form Markdown at all and render it verbatim; this is documented in the module's own docstring now as the reasoning, not just "here's how it works."

### Colleague Irvan's parallel Agent Studio infrastructure — confirmed live, not just code

Irvan has separately built and deployed (confirmed via CAI Applications screenshot, all "Running" for 3-5 days under project "Semantic M...", user `izarkasie`): **Vector DB** (Qdrant), **Graph DB** (Neo4j), and several iterations of **Workflow: TEMPO KPI Analyst** (v1.4.4 through v1.4.6, single-agent/single-tool/no-delegation architecture — see point 5 above). His KPI catalog (`TEMPO_KPI_query_catalog.json`, generated 2026-09-24) has **66 KPIs/measures** cataloged vs our 39 governed metrics — covers our 5 in-scope domains plus promo/pricing/assortment/qa/executive/finance/lead_time. Not yet integrated or reused beyond the `execute_governed_metric_query` architectural pattern above — his tool itself was not called from our workflow. Worth a direct conversation with Irvan about whether his Neo4j/Qdrant instances are meant to be shared infrastructure for this project or his own scoped experiment, and about the `demo_config.py` credential rotation.

### Next planned work (not started yet — this is what the ChatGPT handoff below is for)

The user's explicit next step: **expand the OSSIE semantic layer to the domains that aren't governed yet**, informed by the latest meeting with the Tempo team. Current coverage snapshot (from `datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md`'s 165-question catalog, gitignored but present on disk):

| Domain | Total Qs | Governed now | Needs new Gold view | Out of scope |
|---|---|---|---|---|
| Sales/Sell-In | 15 | 5 | 7 | 3 |
| B2B/Sell-Out | 15 | 11 | 2 | 2 |
| Stock SAT-IDM | 15 | 9 | 6 | 0 |
| SAT OOS | 15 | 6 | 9 | 0 |
| Stock Tempo | 15 | 8 | 7 | 0 |
| Service Level | 15 | 6 | 6 | 3 |
| Unloading | 25 | 9 | 16 | 0 |
| Picking | 25 | 11 | 10 | 4 |
| **SAT Promo** | 25 | **0** | 21 | 4 |
| **Total** | 165 | 65 | 84 | 16 |

SAT Promo has zero coverage (no Gold view exists at all). The user mentioned having fresh input from a recent Tempo team meeting specifically about the Sales domain that hasn't been incorporated yet — that should shape prioritization before building anything.

Older handoff context (3-agent Agent Studio build-out, 25 Sep 2026) is preserved below in the next section — still accurate as history, just no longer the most recent work.

<details>
<summary>Previous handoff note (25 Sep 2026, switching from Claude Code to Codex) — historical, superseded above</summary>

Everything through commit `ec19a8d` is committed **and pushed** to `origin/main` — no local-only commits pending. Recent history (newest first):

```
ec19a8d feat: accept Impala credentials as Agent Studio User Parameters
376da58 fix: lazy-import backend implementations in build_data_backend()
ddb095f feat: add 3-agent Cloudera Agent Studio workflow (Master, Data, Analysis)
eec480a fix: validateChatResponse rejected every response after adding data.unit_format
2ef48b8 feat: generate governed answer narratives with the LLM instead of a static template
283334d fix: format governed metric values by their declared unit, not by field name
d6df38a feat: add LLM fallback for governed metric resolution
9bbff4a fix: relax OSSIE registry validator to a minimum, not an exact count
f450314 fix: add missing langdetect to backend/requirements-lock.txt
eb59d27 fix: sync venv with requirements.txt on every CAI backend start
6734d64 feat: add 9 journey Gold views (Stock Tempo→Sales→B2B→SAT-IDM→OOS) to OSSIE semantic layer
ffc7d4e refactor: make OSSIE/Impala the permanent default, remove legacy semantic layer from the request path
```

**Immediate next step — Agent Studio end-to-end test is mid-flight, not finished:**

The 3-agent Cloudera Agent Studio workflow (`TEMPO Master Agent` → `TEMPO Data Agent` / `TEMPO Analysis Agent`, docs in `projects/tempo_scan_impala/agents/AGENT_STUDIO_3AGENT_SETUP.md`) is now fully built in the UI: all 4 custom tools (`resolve_semantic_object`, `get_metric_definition`, `execute_governed_query`, `execute_readonly_sql`) exist in the Tools Catalog and are attached to TEMPO Data Agent, each with `project_root=/home/cdsw/enterprise-ai-poc` set, and the two Impala-backed tools (`execute_governed_query`, `execute_readonly_sql`) additionally have `impala_host`/`impala_port`/`impala_database`/`impala_auth_mechanism`/`impala_user`/`impala_password`/`impala_use_ssl`/`impala_use_http_transport`/`impala_http_path` filled in as User Parameters (see commit `ec19a8d` for why — Agent Studio's tool Configure UI only exposes User Parameters, no separate env-var section, so credentials are threaded through `UserParameters` → `os.environ` inside each tool before `Settings()`/`TempoOssieService()` is constructed).

Testing via the full agent conversation ("Berapa Gross Sales Q4 2024?") initially showed `resolve_semantic_object` failing inside the Data Agent. **Root cause confirmed and resolved (25 Sep 2026, later same day)**: it was a stale CAI Workbench checkout predating the `376da58`/`ec19a8d` fixes — after `git pull origin main` in the Workbench terminal, the exact same manual command now succeeds cleanly:

```bash
cd /home/cdsw/enterprise-ai-poc
python3 projects/tempo_scan_impala/agent_studio_tools/resolve_semantic_object/tool.py \
  --user-params '{"project_root": "/home/cdsw/enterprise-ai-poc"}' \
  --tool-params '{"question": "Berapa Gross Sales Q4 2024?"}'
# -> {"status": "resolved", "metric": "gross_billing_value", "matched_alias": "gross sales",
#     "definition": {..., "unit_format": "currency_idr", ...}}
```

This confirms the `duckdb` lazy-import fix, the LLM-fallback resolver, and `unit_format` are all working correctly against the real CAI environment. **Not yet done**: this was validated via the manual terminal command only, not yet re-tested through the full Agent Studio agent conversation (the earlier UI test predates this fix). Next actions, in order:

1. Re-run the same "Berapa Gross Sales Q4 2024?" question through the actual Agent Studio conversation (not the terminal) and confirm TEMPO Data Agent now succeeds end to end (resolve → get_metric_definition → execute_governed_query, the last one requiring the Impala credentials configured in `ec19a8d` to actually connect and return real Q4 2024 numbers).
2. If `execute_governed_query` or `execute_readonly_sql` show trouble (these are the only 2 of the 4 tools that touch Impala), validate them individually with the same manual-terminal-first approach before assuming the agent conversation UI's error is the full story.
3. Once the governed path works end to end, run the full test scenarios from `AGENT_STUDIO_3AGENT_SETUP.md` §4 (governed path, ungoverned SQL-fallback path via `execute_readonly_sql`, and the negative-control `DROP TABLE` rejection).

**Known Agent Studio quirks hit so far** (all worked around, not blockers):
- Gemini as the LLM backend threw `litellm.BadRequestError ... "Requests ending with a model turn are not supported"` specifically when the Manager Agent delegated to a sub-agent (not on direct replies) — switching to a GPT model in the same workflow made this go away; root cause in Agent Studio's Gemini message formatting was not investigated further.
- The combined system prompt across all 3 agents exceeded Qwen3.8-27B-AWQ's 4096-token context window before any tool was even attached — fixed by shortening each agent's Backstory to terse bullet points (routing rules, numbered pipeline, gates) rather than prose. If more agents/tools are added later and this recurs, shorten further or pick a larger-context model if one becomes available.
- This version of Agent Studio (v2.3.0-b40) has no separate "Tools Playground" for isolated per-tool testing before attaching to an agent — validate tools either by running `tool.py` manually in a Workbench terminal (fastest for real errors) or by testing through the full agent conversation. The agent conversation UI only ever shows the agent's own friendly fallback wording on tool failure, never the underlying Python traceback — always cross-check with a manual terminal run when something looks wrong.
- Each tool's Configure UI in Agent Studio only exposes fields declared in that tool's `UserParameters` Pydantic model — there is no separate environment-variable configuration surface per tool. Any external config a tool needs (Impala credentials, feature flags, etc.) must be declared as an explicit `UserParameters` field and copied into `os.environ` inside `run_tool()` before importing anything from `backend/app/`.

Older handoff context (OSSIE/Impala cutover, 24 Sep 2026) is preserved below in "Live Impala cutover + resolver fixes + legacy cleanup (24 Sep 2026)" further down this file — still accurate, just no longer the most recent work.

This is a running snapshot to paste into ChatGPT (where the original plan/milestones live) to sync it with what's actually been built.

</details>

---

## Architecture (as built)

Three deployed CAI Applications, one shared FastAPI backend:

1. **tempo-frontend** — Next.js 15 (App Router), TypeScript, Tailwind, Recharts. Pages: Dashboard, Ask AI, AI Monitoring, Settings.
2. **tempo-backend** — FastAPI + LangGraph orchestration (`backend/app/graph/`). Serves `/api/dashboard`, `/api/chat`, `/api/health`.
3. **qwen-38-awq / vLLM Application** — `testing/model/vllm/` — self-contained CAI Application: builds its own venv, starts `vllm serve` with `--reasoning-parser qwen3 --default-chat-template-kwargs`, then a FastAPI proxy in front of it (message normalization for Agent Studio/LiteLLM compatibility).
4. **(optional) LiteLLM routing layer** — `litellm/` — 4th CAI Application, routes through a `commercial-intelligence` model group with an `agent-studio-workflow` placeholder group that falls back to `commercial-intelligence` if unavailable. Default-off, backward compatible.

**Data backend & semantic layer (current defaults, changed 24 Sep 2026)**:
`backend/app/core/config.py` now defaults to `project_id="tempo_scan_impala"`, `semantic_execution_mode="ossie"`, `data_backend="impala"`. OSSIE/Impala — governed real TEMPO Q4 2024 data via Apache Ossie — is the permanent path for Ask AI and the Dashboard, not an opt-in profile anymore. The old DuckDB-synthetic semantic layer (`app/semantic/{resolver,intent}.py`, the SQL-generation/graph nodes it powered) has been deleted from the live request path entirely.

**Forecast / weather / market intelligence — kept but disconnected**: these three modules (`app/forecasting/`, `app/external_signals/weather/`, `app/market_intelligence/`) still query DuckDB-synthetic tables directly and have not been retargeted to Impala. Rather than delete them, they were explicitly excluded from this cleanup (forecasting is a standing tool the user wants kept by default; market intelligence's data relevance is still an open question — both to be discussed separately). Their code, tests, and `projects/tempo_scan/semantic/*.yaml` config all remain intact, but `route_intent`/`workflow.py` no longer route anything to them — they are unreachable from Ask AI until a future decision is made. Internally they now read `settings.legacy_synthetic_project_id` (`"tempo_scan"`, a new dedicated setting) instead of the shared `project_id` default, since that default now points at `tempo_scan_impala`.

**Conversation memory**: custom `ConversationStore` (`backend/app/services/conversation_store.py`) — plain synchronous SQLite, `MAX_HISTORY_MESSAGES = 20`. (A LangGraph `AsyncSqliteSaver` checkpointer was tried first and abandoned — it had a correctness bug causing exponential checkpoint file growth, several GB within minutes. Documented as a hard "don't retry this" in project memory.)

**Guardrails**: Guardrails AI (`guardrails-ai` package + Hub validators `DetectJailbreak`, `SecretsPresent`), auto-installed at CAI Application startup via `ensure_guardrails()` in `backend/app_cai_backend.py`, gated by `GUARDRAILS_ENABLED`/`GUARDRAILS_TOKEN` env vars.

---

## What's done (chronological, condensed)

**Backend correctness/governance fixes** (the biggest chunk of work):
- Fixed the AI fabricating answers with the wrong metric (e.g. answering "how many customers" with a Net Sales figure) instead of admitting data isn't governed. Two rounds, root-caused as `measure_request_terms` list gaps + `route_intent` and `resolve_semantics` using divergent keyword sets.
- Fixed a systemic language-detection bug: 7 places compared `state["language"] == "id"` directly, but the frontend always sends `"auto"`, so every deterministic fallback silently defaulted to English. Fixed via one `_resolve_language()` helper.
- Fixed evidence table columns/data getting mixed up across conversation turns in the same session (React state bug: `state.chat.table.columns` was global, shared by every rendered message).
- Fixed caveats (governance/data-availability disclaimers) never reaching the UI at all. The field existed in API responses but no component rendered it. Also had to strip raw internal status codes (e.g. `METRIC_NOT_CONFIGURED`) that would have leaked into caveats once rendering was added.
- Fixed a guardrail bypass: phrasing like "data customer tidak governed, kasih tau aja" was quietly answered instead of getting an explicit disclaimer.
- Fixed forecast/weather fallback responses: language inconsistency, and irrelevant "recommended actions" showing up when there was no data to act on.
- Made `direct_chat` (greetings/small talk) call the LLM for a natural reply instead of a fixed template, so it can actually respond to whatever was asked ("bisa bahasa Indonesia?", "siapa kamu?") instead of only recognizing hardcoded greetings.
- Robotic phrasing fixed: raised `ANALYSIS_TEMPERATURE` to 0.35, added a `CONVERSATIONAL_TEMPERATURE` of 0.5, rewrote system prompts for natural analyst/colleague phrasing.

**UX/product fixes**:
- `npm ci` no longer re-runs on every frontend restart (marker file).
- Fixed 5 UX issues in one pass: floating AI not syncing to dashboard, "New Chat" not creating real sessions, floating→Ask AI handoff re-triggering the same question, follow-ups not working, no persistent memory.
- Renamed the assistant to **SCAN** (Smart Commercial Analytics Navigator) throughout.
- Added a "SCAN Test Plan" artifact (~50 manual test scenarios across greeting, analytical, metric-unavailable, forecast, weather/market, out-of-scope, guardrail, multi-turn, visualization, session-management categories). Used to drive most of the correctness fixes above.

**vLLM / Agent Studio incident (biggest single debugging session)**:
- Agent Studio kept failing with `litellm.BadRequestError: System message must be at the beginning.` Took a long path through several wrong hypotheses (proxy message-ordering, missing vLLM CLI flags, corrupt venv, missing compiler for a Triton kernel) before finding the real root cause: `_resolve_base_dir()` in `app.py` used a wildcard glob (`base.glob("*/vllm")`) that could silently match an old, abandoned folder (`/home/cdsw/tempo_llm_vllm_test/vllm/`) instead of the real project folder, so the Application was sometimes launching uvicorn against stale, unfixed code no matter how many times it was restarted or even recreated from scratch. Every file-content check looked correct because it was always checking the *intended* checkout, not the one actually running.
- Diagnosed by adding a throwaway `/debug-version` endpoint + build marker to the proxy and curling it directly. A 404 was the proof that stale code was serving traffic.
- Fixed with an exact, non-wildcard path check. Confirmed working via direct curl tests (including a deliberately out-of-order `[user, system, user]` payload) and then in Agent Studio itself.
- Along the way also fixed: `app.py` now builds its own project-local venv instead of depending on a global `vllm` install (`~/.local`) that doesn't survive a CAI container rebuild; auto-rebuilds the venv if it's corrupt/incomplete; passes `--reasoning-parser qwen3 --default-chat-template-kwargs` to `vllm serve` (needed for this specific model's GDN/reasoning architecture).
- Lesson captured in project memory: if a CAI Application keeps behaving like it's running different code than what's on disk, don't trust `git log`/file-content checks alone. Add a version-marker endpoint and curl it, since that's the only way to prove what a *running process* actually loaded.

**UI/product decision — floating AI removed**:
- The Dashboard's floating "Ask AI" chat drawer was removed entirely after a UX review. It duplicated Ask AI's chat UI almost exactly (same fields, different markup), used a separate session, and needed a manual "Continue in Ask AI" handoff. Confusing, and already drifting (caveats had been added to one and not the other).
- **Ask AI is now the single chat surface.** It still applies AI-driven dashboard state changes (filters, highlights) via `applyDashboardAiActions`, carries undo history, shows as "Applied by AI" with a working Undo on the Dashboard even though the chat that triggered it lives on a different page.
- Dead code removed: `DashboardAssistant`, `DrawerAnswer`, `dashboardAiActions.ts` (deleted outright), the drawer-only focus-scroll mechanism, the sessionStorage chat handoff.

**Latest round — tone, icons, layout polish (most recent)**:
1. SCAN's conversational tone made warmer/more casual (system prompts now explicitly ask for "sharp colleague," not "formal corporate assistant"), locked to **saya/Anda** consistently. An earlier pass let it drift to aku/kamu mid-conversation, which read as inconsistent rather than warm. Fixed on user feedback after live testing.
2. Em dashes (—) and en dashes (–) explicitly banned from all LLM-generated output (both conversational and analytical system prompts). Was reading as visibly AI-generated.
3. (Not a code change, a recommendation) The Agent Studio "General Prompt / System Instruction" field is separately editable in the Agent Studio UI itself. Gave the user a rewritten draft prompt matching the same warmer, no-em-dash voice.
4. Replaced the generic Sparkles/Bot icons in Ask AI with a plain "S" monogram (`ScanMark` component). Matches the avatar pattern already used for the user's own initials and the sidebar brand mark, reads as part of the product instead of a generic AI widget.
5. Removed the Dashboard's page title/subtitle (`PageIntro`). Filters now sit directly under the app shell header instead of under a repeated "Commercial Dashboard" heading. "Last refreshed" moved into the filter row.
6. Sales Performance chart card split: line chart (left) + a metrics panel (right) showing Best month, Period average, Latest month-over-month move, and Forecast delta when available. Computed client-side from existing trend data, no backend change needed. Previously it was just a bare line chart.
7. Body font switched from Inter (near-universal AI-tool-template default) to **Plus Jakarta Sans** via `next/font/google`, self-hosted.
- User reviewed the result live and confirmed it reads as natural now, with one fix requested (pronoun consistency, #1 above, already applied).
- Also confirmed: the current Ask AI message bubble layout (user bubble right-aligned within its own max-width, AI card left-aligned within its own max-width, both within a full-width panel) is **intentionally kept as-is**. A comparison against Gemini's centered-narrow-column style was raised and then explicitly rejected in favor of the current layout.

---

## TEMPO real-data Impala + Apache Ossie profile (24 Sep 2026)

This is a **parallel, default-off migration path**. It does not overwrite the
existing `tempo_scan` synthetic foundation.

### Physical and semantic audit

- Existing CDP pipeline confirmed: 12 Silver Iceberg tables and 36 Gold views.
- Sales scaling confirmed: Silver Sales values are 1/100 IDR; Gold applies
  ×100 exactly. Official revenue remains `BILL_VAL` / Gross Billing Value.
- `gold.rpt_sap_material_month` grain (`calmonth + material`) validated unique.
- Five audited semantic wrapper views were created in Impala:
  - `gold.rpt_sap_monthly_executive_semantic`
  - `gold.rpt_sap_material_month_semantic`
  - `gold.rpt_service_level_material_month_semantic`
  - `gold.rpt_sap_customer_reconciliation_semantic`
  - `gold.rpt_sales_office_performance_semantic`
- Runtime metadata view: `gold.rpt_semantic_metric_catalog`.
- Semantic Contract v1: 28 metric definitions across 5 views.
  - 21 adapted from Irvan's KPI catalog.
  - 7 derived during audit.
  - 26 pending TEMPO business confirmation.
  - 2 internal technical/data-quality metrics.
- Source-controlled DDL, audits, field catalog, provenance, and final checks:
  `datasets/audit/`.

### Isolated real-data project

New profile: `projects/tempo_scan_impala/`.

- Official Apache Ossie root-schema model: 5 datasets, 28 metrics.
- Governance rules: Q4 scope, Sell-In/Sell-Out ambiguity, official revenue,
  no free SQL, no invented joins.
- 31 candidate management/golden questions with supported, clarification,
  unsupported, and blocked outcomes.
- Current candidate coverage: 19 supported/supported-with-caveat, 1
  clarification, 10 intentionally unsupported scope tests, 1 blocked free-SQL
  request. A real 30–50 question management inventory is still required.
- Apache Ossie official schema validation: **PASS**.
- Internal semantic contract validation: **PASS**.

### Additive backend/runtime

- New `backend/app/ossie/` registry, resolver, deterministic compiler, query
  executor, and LangGraph nodes.
- New read-only API surface:
  - `/api/semantic/status`
  - `/api/semantic/capabilities`
  - `/api/semantic/resolve`
  - `/api/semantic/ontology`
  - `/api/semantic/join-path`
  - `/api/semantic/compile`
  - `/api/semantic/query`
- Feature flag remains default-off:

```text
SEMANTIC_EXECUTION_MODE=legacy
OSSIE_PROJECT_ID=tempo_scan_impala
```

- OSSIE execution requires `DATA_BACKEND=impala`; no ungoverned fallback is
  attempted.
- Existing canonical `ChatResponse` metadata shape was deliberately preserved
  after regression caught an attempted additive change.
- Impala backend now reports real latency and wraps driver failures in safe
  `IMPALA_QUERY_FAILED` errors.

### Agent Studio and UI

- Five non-graph Agent Studio tools added under
  `projects/tempo_scan_impala/agent_studio_tools/`.
- PuppyGraph remains explicitly deferred.
- Ask AI shows Q4 capabilities and real-data examples only when OSSIE mode is
  enabled.
- Dashboard reuses the existing component shell but switches to Gross Sales,
  Fill Rate, Material, Sales Office, and Sell-In/Sell-Out context for the
  Impala profile.
- Forecast, weather, and market claims are hidden in the real-data profile.
- Legacy synthetic Dashboard and Ask AI behavior remain unchanged by default.

### Validation evidence

- Backend full suite: **376 passed**, 2 dependency deprecation warnings.
- Frontend full suite: **56 passed**.
- Frontend TypeScript: **no errors**.
- Linter diagnostics for changed files: **none**.
- Official OSSIE validation: **PASS**.
- Live Impala acceptance script:
  `scripts/validate_tempo_impala_live.py`.
- CAI deployment/rollback runbook:
  `docs/tempo-impala-ossie-runbook.md`.

### Still requires the CAI environment

- Upload and validate the five Agent Studio tools in Tools Playground.
- Collect 30–50 real TEMPO management questions.
- Obtain business approval for candidate metrics.

---

## Live Impala cutover + resolver fixes + legacy cleanup (24 Sep 2026)

Real-data cutover happened this session, superseding the "still requires the CAI environment" list above.

**Live Impala connectivity**: connected `tempo-backend` to the real CDP Impala Virtual Warehouse (LDAP/workload password, HTTP transport over port 443/`cliservice`, not the binary Thrift default). Added `impala_use_http_transport`/`impala_http_path` settings. Credentials live only in the CAI Application's Environment Variables UI, never committed.

**Root-caused and fixed a "5 files never committed" bug**: `dashboard.py`, `graph/{nodes,state,workflow}.py`, `core/schemas.py` had been edited in an earlier session but never `git add`ed (they were tracked-modified "M", not untracked "??", so a prior `git add <new-dir>` silently skipped them). This broke both Dashboard and Ask AI in OSSIE mode simultaneously. Found via a new `/api/debug/settings` diagnostic endpoint (`backend/app/api/routes/health.py`) that distinguishes "wrong config" from "stale/incomplete deployment" — same technique used in an earlier vLLM debugging session.

**Fixed a 10x baseline error** in `scripts/validate_tempo_impala_live.py`'s `EXPECTED_Q4_GROSS_SALES` constant (transcription error, not a data bug — the Gold-layer `×100` scaling chain was independently verified correct via `datasets/audit/*.sql`).

**Fixed two real bugs in `TempoOssieRegistry.resolve_metric()`** (`backend/app/ossie/registry.py`), found via a 5-question manual audit comparing a Python audit script's output against live Ask AI:
1. Word-order-sensitive exact-substring matching meant "nilai Sell-In terbesar" didn't match a synonym written as "material sell-in value" even though every content word was present. Fixed by adding token-overlap matching as a second, lower-priority match mode (substring matches still always outrank token-only matches).
2. "Fill Rate per bulan?" resolved to a granular per-material metric instead of the company-wide aggregate, because `company_fill_rate` had no bare "fill rate" synonym. Fixed by adding the synonym plus a scoring bonus for aggregate metrics when no other dimension qualifier is present.

**Delivered the exact user-specified greeting spec** (`backend/app/ossie/graph_nodes.py`'s `ossie_conversational`): shown once per session (gated on `state["history"]` being empty), with the 4 fixed example questions, then a short reply on later turns.

**Removed the legacy semantic layer from the live request path** (this was scoped down through discussion — see below):
- Deleted from `backend/app/graph/nodes.py`: `resolve_semantics`, `metric_unavailable`, `normalize_intent`, `generate_sql`, `repair_sql`, `validate_sql`, `execute_sql`, `result_checker`, `analyze_result`, `visualization_planner`, `ui_action_generator`, `direct_chat`, and the legacy keyword-routing tail of `route_intent` (now just greeting-vs-analytical → `ossie_conversational`/`ossie_analytical`).
- `backend/app/graph/workflow.py` rewired to only register `input_guard → route_intent → {ossie_analytical, ossie_conversational} → output_guard`, plus `fallback`.
- `backend/app/services/dashboard.py`: `get_dashboard_overview()` now calls the OSSIE path unconditionally; ~130 lines of legacy dashboard-query-building code deleted (`_load_dashboard_config`, `_validated_filters`, `_period_for`, `_build_query`, `_rows`).
- **Explicitly NOT deleted** (still used by the retained forecast/weather/market): `app/semantic/{loader,models}.py`, `projects/tempo_scan/semantic/*.yaml`. `app/semantic/{intent,resolver}.py` and `app/tools/{semantic_sql,chart_builder}.py` also stay, because `app/bootstrap/validation.py` (a separate synthetic-data-loading/validation harness, not part of the live request path) still imports them — out of scope for this cleanup, flagged but not touched.
- Deleted 4 test files that exercised only the removed legacy pipeline (`test_nl_to_sql.py`, `test_shared_context.py`, `test_shared_context_integration.py`, `test_query_service.py`); updated ~10 more that assumed legacy-mode defaults or routing.

**Made language detection more robust** (`backend/app/ossie/graph_nodes.py`'s `_language()`): added the `langdetect` library as a fallback for longer, keyword-less questions, keeping the existing exact-phrase greeting check first (langdetect is unreliable on 1-3 word inputs like "Halo"/"Hi" — verified empirically before deciding this). This replaces an ever-growing manual keyword list with real language identification for anything past a greeting.

**Config defaults changed** (`backend/app/core/config.py`, `.env.example`): `project_id` → `"tempo_scan_impala"`, `semantic_execution_mode` → `"ossie"`, `data_backend` → `"impala"`. Added `legacy_synthetic_project_id` (`"tempo_scan"`) so forecast/weather/market keep resolving their synthetic project explicitly rather than following `project_id` if it changes again.

**Validation**: backend full suite 337 passed (was 376 before the legacy-test deletions — the delta is entirely removed dead-code tests, not lost coverage of anything still reachable). Offline OSSIE/Impala contract validation: PASS.

**Explicitly out of scope this session** (per user's own scoping decisions, to revisit separately):
- Whether/how to retarget `forecasting/` to Impala (needs a new Gold-layer forecast table) vs. keep it on synthetic DuckDB.
- Whether `market_intelligence/`'s data (currently unfilled/unvalidated synthetic SerpAPI/Serper skeleton data) is worth keeping or filling.
- The planned new Agent Studio workflow connected to LiteLLM routing (mentioned once, not started).

---

## Milestone checklist

Reconstructed against the CAI/vLLM/Trino milestone framing from the ChatGPT-side plan (M-numbers approximate — align exact numbering with ChatGPT's own doc).

**Done**
- [x] M?: Qwen model deployed to CAI as its own Application, serving OpenAI-compatible `/v1/chat/completions`
- [x] M?: Qwen model registered in Agent Studio (full model path + explicit `https://` API Base — fixed earlier in the project)
- [x] M7.2: Split CAI Deployment — FE CAI App (tempo-frontend), BE CAI App (tempo-backend), Qwen CAI App (qwen-38-awq/vLLM) all live as separate Applications
- [x] Backend orchestration (LangGraph), semantic/governance layer, conversation memory (custom SQLite store), guardrails auto-install — all built and working on top of the split deployment
- [x] Agent Studio + vLLM compatibility bug (`System message must be at the beginning`) — root-caused and fixed (see incident summary above)
- [x] ~50-scenario manual test pass across greeting/analytical/forecast/guardrail/etc — used to drive a long list of correctness fixes (metric fabrication, language fallback, table-column bleed, missing caveats, guardrail bypass)
- [x] UX cleanup: floating AI drawer removed, Ask AI is the single chat surface, dashboard state still updates from it
- [x] Voice/visual polish: warmer consistent tone, no em dashes, custom "S" monogram icon, dashboard title removed, trend chart split with a metrics panel, custom font (Plus Jakarta Sans)
- [x] TEMPO Impala semantic data audit: 5 business-facing semantic views, 28-metric governed catalog, lineage/provenance, precision and grain validation
- [x] Additive Apache Ossie profile: official-schema model, governance, 31 golden questions, deterministic backend runtime, five Agent Studio tools, and default-off frontend profile
- [x] Foundation regression after OSSIE integration: backend 376 passed, frontend 56 passed, TypeScript clean
- [x] Live CAI Impala/Ossie connectivity and cutover — Impala credentials configured in CAI, live validation passing, `PROJECT_ID=tempo_scan_impala`/`DATA_BACKEND=impala`/`SEMANTIC_EXECUTION_MODE=ossie` are now the code defaults (not just env overrides)
- [x] Legacy DuckDB-synthetic semantic layer removed from the live Ask AI/Dashboard request path (see "Live Impala cutover + resolver fixes + legacy cleanup" above)

**Not started**
- [ ] Original M5.6/M8 Trino synthetic foundation remains unstarted and is no longer the immediate real-data path; the new Impala/Ossie profile is the current priority.
- [ ] LiteLLM Application confirmed end-to-end with a real Agent Studio workflow behind the `agent-studio-workflow` model group (it's deployed but that group is currently just a fallback placeholder, never exercised against a live workflow)
- [ ] Guardrails Hub validators (`DetectJailbreak`, `SecretsPresent`) confirmed installed and active in a real CAI Application run with `GUARDRAILS_ENABLED=true` (automated into startup, but the install step itself was never verified from outside a network-restricted sandbox)
- [ ] Revisit the "one bundled Application vs. 3-4 split Applications" tradeoff — user noted split deployment is what got built, but had separately said one bundled process is easier to troubleshoot; not reconciled against the M7.2 plan in this session
- [ ] forecasting/market_intelligence Impala retargeting decision (explicitly deferred, see above)
- [ ] Planned new Agent Studio workflow connected to LiteLLM routing (mentioned once, not started)

---

## Known state / not yet done

- **Default deployment is now Impala/OSSIE real data.** The old DuckDB-synthetic Ask AI/Dashboard path was removed from the live request path this session (24 Sep 2026); `tempo_scan`'s synthetic data and semantic YAML remain on disk only for forecast/weather/market intelligence and the standalone `app/bootstrap/` loader, not for Ask AI. The older Trino synthetic foundation remains unstarted and is not the immediate cutover path.
- Per the screenshot shared this session, the user's current milestone framing (from the ChatGPT-side plan) is:
  - **M7.2 Split CAI Deployment**: FE CAI App, BE CAI App, existing Qwen CAI App. This matches what's actually deployed (3 apps, or 4 with the optional LiteLLM layer).
  - Then **M5.6 / M8: Live Trino Data Foundation**: determine catalog/schema, create tables, populate synthetic sales/weather/market-intelligence/forecast data, validate golden queries, switch backend `DATA_BACKEND=trino`.
  - User's own stated preference (from the screenshot): bundling the 3 processes into one Application is "jauh lebih enak buat troubleshooting" than 3 separate ones. Worth surfacing back to ChatGPT as input to the plan, since the actual deployment ended up as 3-4 *separate* CAI Applications instead, for reasons never fully reconciled against that stated preference in this session.
- Agent Studio model registration (Qwen path) was fixed earlier in this project's history (full model path + explicit `https://` in API Base) and is marked working, separate from the later vLLM Application bug described above.
- LiteLLM Application is deployed but optional/default-off, not confirmed end-to-end with a live Agent Studio workflow behind it (the `agent-studio-workflow` model group is currently a fallback-to-`commercial-intelligence` placeholder).
- Guardrails Hub validator installation was authenticated and automated into CAI startup, but was never verified working end-to-end from outside the sandbox environment used mid-project (network restriction blocked verifying the install step directly). Needs a real check with `GUARDRAILS_ENABLED=true` set.

---

## Reference paths

- Backend entrypoint: `backend/app_cai_backend.py`, orchestration in `backend/app/graph/`
- Frontend: `frontend/src/views/{DashboardPage,AskAIPage}.tsx`, shared state in `frontend/src/lib/dashboardState.tsx`
- vLLM Application (the one with the glob bug, now fixed): `testing/model/vllm/{app.py,proxy.py}`
- Trusted reference vLLM setup (different model, Qwen3.5-9B, used as a pattern reference during the debugging session): `account/data intelligence/vllm/`
- LiteLLM: `litellm/{app_cai_litellm.py,config.yaml}`
- Governed OSSIE model/config (the live Ask AI path): `projects/tempo_scan_impala/ossie/{tempo_core.ossie.yaml,tempo_governance.yaml,golden_questions.yaml}`
- OSSIE backend runtime: `backend/app/ossie/{registry,service,graph_nodes}.py`
- Legacy synthetic project (now only used by forecast/weather/market, kept intact but disconnected from routing): `projects/tempo_scan/semantic/*.yaml`, `backend/app/forecasting/`, `backend/app/external_signals/weather/`, `backend/app/market_intelligence/`
- Standalone synthetic-data bootstrap/validation harness (separate from the live request path, untouched by the OSSIE cleanup): `backend/app/bootstrap/`
- Audited Impala semantic DDL/catalog: `datasets/audit/`
- CAI runbook: `docs/tempo-impala-ossie-runbook.md`
- Diagnostic endpoint for "is this a stale process or a bad config value": `GET /api/debug/settings` (`backend/app/api/routes/health.py`)
