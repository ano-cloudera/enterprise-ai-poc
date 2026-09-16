# Controlled Natural-Language-to-SQL

```text
Question
  → deterministic semantic resolution
  → Pydantic Structured Analytical Intent
  → configured period/comparison normalization
  → SQL AST compilation
  → authoritative SQL validation
  → QueryService read-only execution
  → result-quality check
  → grounded answer
  → deterministic chart and UI actions
```

Raw question text does not control SQL structure. In local mock mode, SQL is compiled exclusively from the normalized intent and validated semantic project. The six supported patterns are KPI, trend, breakdown, top/bottom contribution, period comparison, and entity comparison.

The result checker returns one internal controlled state: `OK`, `EMPTY`, `INSUFFICIENT_DATA`, or `INVALID_RESULT`. Analysis runs only for `OK`. Comparison results require `current_value`, `previous_value`, `absolute_change`, and `percentage_change`, and a usable previous-period denominator. The graph permits at most one SQL repair attempt.

## Worked example

Question: `Kenapa sales Jawa Barat turun bulan ini?`

Normalized intent:

```json
{
  "intent_type": "analysis",
  "pattern": "period_comparison",
  "metric": "net_sales",
  "dimensions": ["region"],
  "filters": {"region": ["Jawa Barat"]},
  "time": {"period": "current_month", "grain": "month", "start": "2024-03-01", "end": "2024-04-01"},
  "comparison": {"type": "previous_period", "period": "previous_month", "start": "2024-02-01", "end": "2024-03-01"},
  "sort": [],
  "limit": 50
}
```

The AST compiler generates a single `SELECT` over `commercial_sales_daily`: it filters `region_name` to the governed value, scans `2024-02-01` through `2024-04-01`, and uses conditional aggregates for current and previous values. The SQL validator confirms the table, columns, date predicates, read-only form, and limit before `QueryService` executes it.

Validated local result:

```json
{
  "region": "Jawa Barat",
  "current_value": 75521.278,
  "previous_value": 90575.469,
  "absolute_change": -15054.191,
  "percentage_change": -16.6206
}
```

Mock analysis states only those returned facts. The visualization planner emits a grouped bar `chart_spec`. The UI action generator emits configured `SET_FILTER`, `SET_DATE_RANGE`, `CHANGE_METRIC`, `CHANGE_DIMENSION`, `HIGHLIGHT_CARD`, `RENDER_CHART`, and `SHOW_TABLE` actions—never executable frontend code.
