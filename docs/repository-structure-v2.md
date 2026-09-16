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
├── projects/
│   ├── tempo_scan/
│   │   ├── semantic/
│   │   ├── branding/
│   │   ├── prompts/
│   │   └── fixtures/
│   └── _template/
├── model-serving/reference-vllm/  # frozen reference only
├── gradio-test/                    # developer test harness
├── specs/
├── docs/
└── scripts/
```

Reusable logic stays outside `projects/`. Customer-specific business semantics and branding stay inside `projects/<project_id>`.
