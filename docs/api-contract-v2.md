# Frontend / Backend Contract v2

## Request

`POST /api/chat`

```json
{
  "question": "Kalau cuma Modern Trade?",
  "session_id": "tempo-demo",
  "language": "auto",
  "history": [],
  "context": {
    "filters": {
      "region": ["Jawa Barat"],
      "channel": [],
      "product": [],
      "category": [],
      "outlet": [],
      "customer_segment": []
    },
    "date_range": {"preset": "current_month", "start": null, "end": null},
    "metric": "net_sales",
    "dimension": "region",
    "highlights": [],
    "ai_applied_context": [],
    "revision": 0
  }
}
```

`dashboard_state` remains accepted as a request-only compatibility alias for `context`. New clients should send `context`.

## Canonical response

```json
{
  "status": "ok",
  "question": "Kalau cuma Modern Trade?",
  "answer": {
    "summary": "...",
    "drivers": [],
    "recommended_actions": [],
    "caveats": []
  },
  "data": {"columns": [], "rows": []},
  "chart_spec": null,
  "ui_actions": [],
  "metadata": {
    "trace_id": "...",
    "session_id": "tempo-demo",
    "intent": "analytical",
    "resolved_context": {},
    "execution_time_ms": 0
  }
}
```

`chart_spec` is either `null` or a validated declarative chart object. UI actions are a discriminated union of the eight documented action types; unknown action types, extra fields, invalid targets, and malformed values are rejected. The frontend runtime-validates chat responses and never evaluates model-generated code.

For analytical requests, `metadata.resolved_context` is derived from the validated normalized analytical intent. The internal analytical intent and validated SQL are not exposed in the public response; they remain controlled workflow state and telemetry/debug concerns.

## Dashboard overview

`GET /api/dashboard/overview` returns the unfiltered default dashboard. `POST /api/dashboard/overview` accepts the same canonical state under `context`; governed filters and date ranges are applied to every configured dashboard query before execution through `QueryService.execute_validated()`.
