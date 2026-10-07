# Repository Structure v2

```text
enterprise-ai-poc/
├── backend/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── graph/              # LangGraph state + nodes + workflow
│       ├── semantic/           # YAML/Pydantic semantic loader
│       ├── db/                 # DuckDB local; Trino/CDW planned for Milestone 5
│       ├── llm/                # provider boundary to Qwen
│       ├── tools/              # deterministic SQL/chart/tool policies
│       ├── guardrails/
│       ├── monitoring/
│       └── services/
├── frontend/
│   ├── app/                    # Next.js App Router
│   └── src/
│       ├── components/
│       ├── layout/
│       ├── lib/                # API + shared dashboard state
│       ├── views/               # page-level components; routes remain in app/
│       └── types/
├── backend-test/               # Exploratory DuckDB agent (optional, :8001)
├── projects/
│   ├── tempo_scan_impala/      # OSSIE model, Agent Studio tools (primary)
│   ├── tempo_scan/             # Synthetic DuckDB semantic + fixtures
│   └── _template/
├── backend/eval/               # UAT YAML + merged JSON reports
├── datasets/gold/              # Gold view DDL (Impala)
├── model-serving/reference-vllm/  # frozen reference only
├── specs/
├── docs/
└── scripts/
```

Reusable logic stays outside `projects/`. Customer-specific business semantics and branding stay inside `projects/<project_id>`.
