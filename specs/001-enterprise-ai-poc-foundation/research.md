# Research / Decisions

## LangGraph vs LangChain

Chosen: LangGraph for orchestration. The desired flow is a state machine with mandatory validation steps and bounded retries. LangChain utilities can be added where helpful, but a generic autonomous agent executor is not the control plane.

## Semantic layer

Chosen: YAML + Pydantic. This keeps the PoC transparent, Git-friendly, SQL-engine-aware and reusable. A heavier semantic product can replace it later if requirements justify the operational cost.

## Local data

Chosen: DuckDB to keep the full hero flow runnable without customer infrastructure. It uses business-ready table names that the planned Trino/CDW mapping can preserve.

## Guardrails

Chosen: deterministic policy first, Guardrails AI second. Prompt-injection checks and output leakage checks can use Guardrails AI, while SQL safety remains an application-side parser/allowlist policy.

## Frontend identity

Chosen: dominant white UI with Cloudera orange, deep navy and violet accents. Tempo Scan remains the active project/customer context while the visual system is reusable across PoCs.
