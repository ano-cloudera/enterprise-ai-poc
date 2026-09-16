# Development Sequence v2

1. Freeze proven Qwen/vLLM serving and keep its API boundary stable.
2. Lock semantic YAML schema, relationships, allowed fields, business definitions, and query rules.
3. Lock v2 chat contract: answer + data + chart_spec + ui_actions + metadata.
4. Implement shared dashboard/conversation state in frontend and backend.
5. Complete LangGraph controlled flow through Semantic Resolver, SQL generation, validation, execution, Result Checker, Qwen analysis, Visualization Planner, UI Action Generator.
6. Validate local hero flow against synthetic trusted data.
7. Connect read-only Trino/CDW and map Tempo real schemas into semantic YAML.
8. Harden SQL validator, query timeout, row limits, logging, and fallback behavior.
9. Polish Next.js UI so dashboard actions visibly react to AI responses.
10. Add forecast tool only after the core analytical flow is stable.
11. Add one external signal only if it improves the demo story.
12. Add monitoring and ground-truth evaluation last.

## Explicitly deferred

CrewAI, unrestricted multi-agent loops, database writes, arbitrary frontend code generation, mandatory Metabase/Wren/BI engines, fine-tuning, complex RAG, and production HA/autoscaling.
