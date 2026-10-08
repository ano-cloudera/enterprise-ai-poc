Referential follow-up on a prior governed result. JSON only.

**Required `turn_kind` (pick one):**
- `new_topic` — full new KPI/ranking in the same chat (bill-to-PO top 10, another domain, top-N list) — not drilling one row from the last chart.
- `continue_session` — drill, filter, tren/per bulan, relimit, compare rows from the last governed result.
- `explain_prior` — why / analisa / penyebab about data already shown (e.g. why November is lowest) — no new SQL.

Use `result_catalog` (ranked entities) and `last_question` / `last_metric` from session.

Set `referential_follow_up=true` when the user points at prior rows (that branch, rank 1 vs last, drill products, etc.).
Fill entity/rank/drill fields from catalog when possible; rewrite `pipeline_question` into explicit Q4 2024 analytic wording.

If the message is a **new topic** — a full governed ask on its own (e.g. “tampilkan 10 material … terendah”, bill-to-PO ranking for a month, another top-N KPI) even in the same chat — set `referential_follow_up=false` and echo `pipeline_question`. Do **not** treat list superlatives (“10 terendah”) as “material rank 1 from the last chart” unless the user says *tadi / itu / dari hasil / ranking itu*.

**Material + per bulan / tren** after a sell-in or Pareto turn (even with an explicit material code like `001-00-03`) is usually **referential** — set `referential_follow_up=true`, bind entity/rank from catalog when possible, `follow_up_material_drill=false`, and keep sell-in context (not a Sell-In vs Sell-Out clarification).

If the message is a new standalone analytic question (not referring to prior rows), set `referential_follow_up=false` and echo `pipeline_question`.

Set `is_conversational=true` only for pure small talk or “what else can you help with?” (no new KPI)—otherwise `false` for analytic follow-ups.
