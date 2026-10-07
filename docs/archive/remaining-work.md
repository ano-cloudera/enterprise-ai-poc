# Remaining Work Before Tempo Demo

The reusable foundation is intentionally ahead of customer integration. The main remaining work is project-specific.

## Must finish

1. Map real Tempo data to business-ready sales and inventory views.
2. Implement and validate read-only Trino/CDW connectivity from the CAI business application in Milestone 5.
3. Set `LLM_MODE=remote` and point the backend to the proven Qwen CAI application.
4. Tune text-to-SQL and executive-analysis prompts against real schema/data.
5. Lock 10-15 golden management questions and expected answers.
6. Test Bahasa Indonesia + English follow-up questions.
7. Build React static bundle and package FastAPI + SPA into the final CAI application.
8. Run failure-path tests: bad SQL, empty result, model timeout, database timeout, guardrail rejection.

## Nice to have after core flow is stable

- validated forecasting model + backtesting
- weather / competitor / market-share signals
- richer quality evaluation
- feedback capture
- advanced session memory

## Keep deferred

- unrestricted autonomous agents
- database write tools
- full MLOps/HA/autoscaling
- vector database unless a document/RAG requirement appears
