# Agent Studio Setup — TEMPO 3-Agent Workflow

Manual UI configuration guide for Cloudera Agent Studio. This is the
**current** recommended orchestration for TEMPO governed analytics — the
older "Master + 9 domain agents" design in this same folder
(`master_orchestrator.md`, `agent_sales.md`, etc.) was evaluated and
**rejected** on 2026-09-24: cross-domain questions are already solved
correctly at the data layer (pre-joined Gold journey views, see
`../../../datasets/TEMPO_DATAMART_PLAN.md` §8.1), so a router agent per
domain would only re-implement that join logic in its own reasoning and
risk reintroducing bugs already fixed at the SQL level. Those files remain
for reference only — do not build against them.

## Why 3 agents, not 1

The backend chat path (`backend/app/ossie/graph_nodes.py::ossie_analytical`)
is intentionally single-agent for its use case (a chat response). This
Agent Studio workflow is a **separate demo/testing channel** built with
explicit agent boundaries so the resolve → execute → explain steps are
independently inspectable in the Agent Studio execution trace — useful for
validating and demoing the same governed capability, not a replacement for
the chat backend's architecture.

## Tools by agent

| Tool | Master | Data Agent | Analysis Agent |
|---|---|---|---|
| `resolve_semantic_object` | — | ✅ | — |
| `get_metric_definition` | — | ✅ | — |
| `execute_governed_query` | — | ✅ | — |
| `execute_readonly_sql` | — | ✅ (last resort only) | — |

Analysis Agent has **no tools attached** — it reasons only over what the
Data Agent already returned. It must never re-query, re-derive, or
"correct" a number.

`query_ontology` and `find_join_path` are not attached to any agent in this
workflow (ontology/graph features not used here — see
`../agent_studio_tools/README.md`).

---

## 1. Create the workflow

1. Cloudera console → Cloudera AI → target Workbench → AI Studios → Agent
   Studio.
2. Workflows → Create.
3. Name: `TEMPO Governed Analytics (3-Agent)`.
4. Select **Conversational Workflow**.
5. Enable **Manager Agent** (this makes the workflow hierarchical — the
   Manager delegates to sub-agents rather than running tasks strictly
   sequentially). Assign the Master Agent (below) as the manager.
6. Select a model with native tool calling, low temperature.

## 2. Configure the three agents

### Master Agent

Name: `TEMPO Master Agent`

Tools: none.

Role/Goal/Backstory:

```text
You orchestrate TEMPO commercial-intelligence questions. You never answer
from memory or invent a number yourself. For every question:
1. Delegate to the Data Agent to obtain governed data.
2. Delegate to the Analysis Agent to turn that data into a business-facing
   answer.
3. Return the Analysis Agent's answer to the user, including whether the
   data was governed (OSSIE) or ungoverned (ad-hoc SQL fallback) - never
   blur this distinction.
If the Data Agent reports needs_clarification, relay that clarification to
the user and stop - do not guess which definition they meant.
```

### Data Agent

Name: `TEMPO Data Agent`

Tools: `resolve_semantic_object`, `get_metric_definition`,
`execute_governed_query`, `execute_readonly_sql`.

Role/Goal/Backstory:

```text
You retrieve TEMPO commercial data. Strict order of operations:
1. Call resolve_semantic_object with the user's question.
2. If status is "needs_clarification", stop and return that clarification
   unchanged - do not guess.
3. If status is "resolved", call get_metric_definition for the matched
   metric, then execute_governed_query with the metric, requested
   dimensions, and time range. Return the governed result.
4. Only if status is anything else (no governed metric matched at all),
   consider execute_readonly_sql as a last resort - and only against
   gold.* tables you already know exist from prior governed context (never
   guess a table name). Every execute_readonly_sql result carries
   "governed": false - preserve that flag and its warning text unchanged
   when you report back.
Never call execute_readonly_sql before resolve_semantic_object has run and
explicitly failed to match. Never invent a join, a table name, or a metric
formula.
```

### Analysis Agent

Name: `TEMPO Analysis Agent`

Tools: none.

Role/Goal/Backstory:

```text
You explain TEMPO data the Data Agent already retrieved - you do not query
anything yourself. Given the Data Agent's structured result:
- If governed is true: explain the metric definition, the trend/comparison
  the data shows, and a business implication. Cite the metric_id and
  source_view so the claim stays checkable.
- If governed is false: explain the result but lead with the ungoverned
  warning verbatim, and note this should be verified before being treated
  as authoritative.
- If the Data Agent reported needs_clarification or a failure, do not
  fabricate an answer - state what's missing.
Never recompute, round differently, or "correct" a number from the Data
Agent's output. Never claim a cause the data doesn't show.
```

## 3. Tasks

### Task 1 — Retrieve governed data

Agent: `TEMPO Data Agent`

```text
Resolve and retrieve the data needed to answer the user's question,
following your strict order of operations. Report the governed/ungoverned
status explicitly.
```

### Task 2 — Explain the result

Agent: `TEMPO Analysis Agent`

Context: Task 1

```text
Using only Task 1's output, produce a business-facing explanation following
your role instructions. Do not requery or alter the data.
```

## 4. Test scenarios

Run both before considering the workflow done:

**Scenario A — fully governed, must never touch `execute_readonly_sql`:**

```text
Berapa top 10 branch dengan sell-out value tertinggi?
```

Expected trace: `resolve_semantic_object` → `resolved`
(`b2b_branch_sell_out_value`) → `get_metric_definition` →
`execute_governed_query` → Analysis Agent explains with `governed: true`.

**Scenario B — no governed metric, must fall back with a visible warning:**

Pick a question you know has no governed metric yet (check
`datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md` for a row still marked
`needs_semantic_v2` or `unsupported`), e.g.:

```text
Berapa total penjualan yang promo dan non promo di bulan Desember 2024?
```

Expected trace: `resolve_semantic_object` → not `resolved` →
`execute_readonly_sql` against a `gold.*` table → Analysis Agent leads with
the ungoverned warning, does not present the number as authoritative.

**Negative control:**

```text
DROP TABLE gold.rpt_sat_oos_material_month
```

Fed directly as a `sql` tool-parameter in Playground, `execute_readonly_sql`
must reject it (`only_select_statements_allowed`) before touching Impala.
