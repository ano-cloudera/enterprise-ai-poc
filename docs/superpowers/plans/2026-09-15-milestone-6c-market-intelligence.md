# Milestone 6C: Market Intelligence Foundation

## Invariants

- Preserve historical analytics, Milestone 6A forecasting, Milestone 6B weather, and model-serving behavior.
- Serper.dev is collector-only; normal application runtime consumes a separately running Mock External Market API. The provider boundary keeps the original design replaceable.
- Keep all live credentials in environment configuration and never emit them in logs or responses.
- Never persist to live Trino in this milestone.
- Clearly distinguish observed digital signals from calibrated synthetic market indicators.

## Strict TDD sequence

1. Add failing tests for SerpApi configuration, normalization, missing values, deduplication, result limits, safe failure, and key redaction.
2. Add failing tests for idempotent snapshot persistence and preservation of the last valid snapshot after collector failure.
3. Add failing tests for deterministic calibrated market generation, provenance, constraints, share consistency, and opportunity components/score.
4. Add failing API tests for health, products, pricing, competitors, share, opportunity, filters, and synthetic-data metadata.
5. Add failing provider/tool tests for structured evidence, unavailable API fallback, and follow-up context.
6. Add failing routing/safety tests proving historical, forecast, and weather routes are unchanged, market routing is deterministic, calculated values are immutable, and fallback contains no invented values.
7. Add at least ten project-owned market golden questions, including missing-data and unavailable-provider cases, and test deterministic resolution.
8. Implement the minimum collector, canonical models, normalization, local repositories, calibrated generator, mock API, runtime provider, market tool, graph route, configuration, and documentation needed to pass each test group.
9. Run the complete backend suite, bundle validation, frontend tests/build, and representative end-to-end scenarios.
10. Run the live snapshot collector only when `SERPAPI_API_KEY` is present; never print or log its value.

## Architecture

```text
Serper.dev (collector only)
  -> validated/deduplicated digital snapshot
  -> local governed persistence
  -> deterministic calibrated market dataset
  -> separate Mock External Market API (:8100)
  -> MarketSignalProvider interface
  -> deterministic Market Intelligence Tool
  -> controlled LangGraph market branch
  -> evidence-grounded response
```

## Opportunity score

Use a documented weighted 0–100 PoC indicator composed of normalized market growth, market size, Tempo share gap, distribution gap, and competitive pressure. Persist and return both the score and components. The score is an analytical PoC construct, not an official commercial methodology.

## Validation

- `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests`
- `.venv/bin/python scripts/validate_bundle.py`
- `npm test` and `npm run build` in `frontend/`
- Collector execution only when the API key is configured
- Separate Mock External Market API endpoint and end-to-end route checks
