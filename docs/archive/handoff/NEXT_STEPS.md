# Historical Next Steps (Superseded)

This pre-foundation handoff is retained for provenance. Milestones 1–4 have completed the sample data, semantic layer, deterministic NL-to-SQL, validation/execution, structured UI actions, and Qwen provider integration. The active next data task is the Milestone 5 Trino/CDW adapter.

1. Lock logical data model
2. Build sample dataset
3. Create Trino/CDW connector
4. Define semantic YAML/JSON
5. Build NL → SQL prompt
6. Add SQL allowlist/validator
7. Execute SQL
8. Return structured result
9. Let Qwen explain
10. Generate chart config

Recommended minimal agent components:
- Router
- SQL Tool
- Insight/Answer Generator

Suggested vibe-coding structure:

```text
tempo-scan-poc/
├── backend/
│   ├── api/
│   ├── agents/
│   ├── tools/
│   ├── semantic/
│   ├── db/
│   └── monitoring/
├── frontend/
├── model-serving/
├── sample-data/
├── tests/
└── docs/
```
