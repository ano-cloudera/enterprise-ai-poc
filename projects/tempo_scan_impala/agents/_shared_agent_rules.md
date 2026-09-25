# Shared rules (include in every domain agent)

## Governed workflow (wajib 2-step)

1. **Plan (text):** grain, metric_id, filters, dimensions, assumptions[] — no tool yet.
2. **Execute:** only `execute_governed_query` after resolve → definition → find_join_path.
3. **Respond:** Temuan → Diagnostik → Preskriptif (if asked) → Batas data → **chart_spec** YAML.

## Global larangan

- No free SQL. No invented joins. No Sales + B2B revenue sum.
- Gold monetary fields are IDR — never multiply by 100 again.
- Scope: October–December 2024 unless promo agent (December SAT only).
- Indonesian: saya/Anda. No em dashes.

## chart_spec template

```yaml
chart_spec:
  question_id: <catalog ID e.g. S02>
  primary: <LINE|HBAR|KPI|...>
  title: "..."
  x: <dimension>
  y: <metric>
  alt: <optional>
  notes: "governed metric ..."
```

Chart types: see `TEMPO_BUSINESS_QUESTIONS_CHART_INDEX.md`.

## Interim assumptions (F0b)

See `datasets/TEMPO_KLARIFIKASI_JAWABAN.md` § PoC interim defaults.
