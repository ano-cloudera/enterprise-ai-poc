# ADR-001: Modular Monolith First

**Status:** Accepted  
**Date:** 2026-10-13

## Context

Accelerator targets PoC/Pilot on Cloudera AI Application with small ops footprint.

## Decision

Implement Cloudera AI Accelerator as a **single FastAPI process** with **domain-oriented packages**, LangGraph in-process, and **optional background workers** only for heavy jobs (parse, embed, sync).

Do **not** split into microservices for M1–M5.

## Consequences

- Simpler CAI deployment and debugging
- Shared transaction boundary for metadata + orchestration
- Vertical scaling first; extract workers only when proven necessary

## Alternatives rejected

- Microservices per domain (connectors, RAG, chat) — ops cost too high for pilot
- Serverless-only — poor fit for long SSE streams and LangGraph state
