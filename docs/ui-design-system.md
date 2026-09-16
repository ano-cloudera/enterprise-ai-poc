# UI Design System

The UI is intentionally closer to a production enterprise product than a notebook/demo UI.

## Visual rules

- 80%+ white/off-white surfaces
- Cloudera orange for primary action and critical highlights
- deep navy for titles, navigation hierarchy and trusted-data framing
- violet reserved for secondary AI/orchestration accents
- subtle borders and shadows, no heavy gradients or glassmorphism
- compact executive dashboards with enough whitespace to stay readable
- charts use orange as the primary series and violet only for secondary series

## Main pages

1. Dashboard
   - executive KPIs
   - sales trend
   - regional breakdown
   - top products
   - channel contribution
   - AI insight panel
2. Ask AI
   - recent conversations
   - structured answer
   - related metrics
   - chart
   - collapsed technical trace
3. Settings
   - model identity
   - language
   - general prompt
   - backend / guardrail status
4. AI Monitoring
   - request count
   - latency
   - success rate
   - SQL rejection rate
   - recent requests

## Deliberately deferred

Grounded-answer %, hallucination risk and user-satisfaction scoring are not faked. Add them only after evaluation data and explicit measurement methodology exist.
