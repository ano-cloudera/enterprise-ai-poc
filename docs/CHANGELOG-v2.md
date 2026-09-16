# v2 Architecture Update

Updated after the Tempo Scan architecture review:

1. LangGraph is the primary orchestrator; CrewAI is excluded from baseline.
2. Graph expanded to Semantic Resolver, Result Checker, Visualization Planner, and UI Action Generator.
3. Chat contract upgraded to `answer + data + chart_spec + ui_actions + metadata`.
4. Shared dashboard/conversation state added for follow-up continuity.
5. UI control is declarative and allowlisted; no arbitrary JavaScript generation.
6. Semantic YAML extended with relationships, allowed fields, and query rules.
7. Frontend target migrated from Vite routing to Next.js App Router.
8. Proven Qwen/vLLM serving remains untouched.

## Milestone 1 — Contract and Execution Safety

1. Locked one Pydantic/TypeScript chat response contract with frontend runtime validation.
2. Replaced generic UI action values with discriminated payload schemas and semantic target checks.
3. Routed chat and dashboard analytical SQL through one validated query service.
4. Hardened SQL table qualification, per-table columns, date filters, functions, stars, relationships, and limits.
5. Moved Tempo resolution entities, periods, and dashboard SQL into the project profile.
6. Added Python 3.10 and npm locks, safe errors/health detail, and contract/security regression tests.

## Milestone 2 — Shared Dashboard State and Structured UI Actions

1. Added one React Context/reducer state shared across Dashboard and Ask AI navigation.
2. Centralized all eight allowlisted UI action mutations, including deterministic single/all reset behavior.
3. Added AI-applied context chips, removable filters, visible KPI highlighting, and safe chart/table rendering.
4. Made dashboard requests state-aware and applied governed filters/date ranges through SQL AST expressions before validated execution.
5. Added config-driven Tempo aliases and follow-up inheritance/explicit override/reset behavior.
6. Added reducer, component, backend, and two-turn integration coverage plus local HTTP smoke validation.

## Milestone 3 — Semantic Resolver and Controlled NL-to-SQL

1. Added a Pydantic analytical intent for patterns, metrics, dimensions, filters, time, comparisons, sorting, and limits.
2. Moved pattern, comparison, grain, period, and entity vocabulary into project YAML.
3. Added deterministic resolution and explicit date/comparison normalization before SQL generation.
4. Replaced mock free-text SQL construction with a governed SQLGlot AST compiler.
5. Added period-comparison measures, controlled result-quality states, grounded mock analysis, and intent-driven chart/UI planning.
6. Added ten project golden questions and NL-to-SQL regression coverage.

## Milestone 4 — Qwen CAI Analysis Provider

1. Added config-selected mock and Qwen OpenAI-compatible providers behind one interface.
2. Added environment-only endpoint/authentication, bounded timeout/retry, safe errors, and reasoning removal.
3. Added compact trusted analysis payloads and strict evidence-bearing structured responses.
4. Restricted Qwen to post-query explanation; semantic SQL remains deterministic in every mode.
5. Added deterministic grounded fallback, safe health representation, model telemetry, and a manual connectivity helper.
6. Updated the future CDW direction from Impala to Trino for Milestone 5 without implementing the connector.
