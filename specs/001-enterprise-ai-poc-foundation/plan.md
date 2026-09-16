# Implementation Plan

## Architecture

The application uses a thin UI, stable FastAPI contract, bounded LangGraph orchestration, project-configured semantic layer, deterministic SQL security, swappable data adapters, and a provider-style LLM client.

## Request flow

```text
User
→ FastAPI
→ Input Guard
→ Intent Router
→ Semantic Context
→ SQL Generation
→ Mandatory SQL Validation
→ Read-only Query
→ Result Check
→ Qwen Analysis
→ Chart Builder
→ Output Guard
→ Structured Response
```

Forecast questions use a separate bounded forecast node. Conversational questions use a direct LLM node but are told not to invent company metrics.

## Reuse boundary

Reusable:
- API contracts
- orchestration
- SQL policy
- semantic loader
- data adapters
- LLM client
- monitoring
- frontend shell/components

Project-specific:
- branding
- semantic datasets/metrics/dimensions
- system prompt
- fixtures
- golden questions
- later forecast/external-signal configuration

## Risk controls

- SQL security cannot be bypassed by tool choice.
- LLM retries are bounded.
- Query row count is capped.
- Database credential remains backend-only and should be read-only.
- Guardrails AI is additive, not the primary security control.

## v2 Plan Amendment

Add Semantic Resolver, Result Checker, Visualization Planner, and UI Action Generator to the controlled LangGraph. Migrate the frontend target to Next.js App Router. Preserve the existing Qwen/vLLM model-serving boundary unchanged.
