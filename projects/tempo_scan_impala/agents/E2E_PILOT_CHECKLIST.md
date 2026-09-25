# E2E Pilot — 10 pertanyaan (F2 gate)

Jalankan di Agent Studio setelah Master + sub-agents terpasang. Setiap baris: **Plan → execute_governed_query → jawaban + chart_spec**.

| # | Domain | catalog_id | Pertanyaan | Expected |
|---|--------|------------|------------|----------|
| 1 | sales | S01 | Berapa total gross revenue Sell-In Q4 2024? | supported + KPI chart_spec |
| 2 | b2b | B06 | Rasio Sell-Out vs Sell-In per material? | supported + SCATTER |
| 3 | stock_sat_idm | I03 | Split stok DC vs store per dcname? | unsupported + redirect |
| 4 | sat_oos | O01 | Persen OOS stok akhir nol? | unsupported + assumption OOS=0 |
| 5 | stock_tempo | T02 | Top material stok gudang Des? | supported + PARETO |
| 6 | service_level | L01 | Fill rate company per bulan? | supported + LINE |
| 7 | picking | KQ1 | Office picking delay rate tertinggi? | supported_with_caveat + HBAR |
| 8 | unloading | UQ1 | Cabang unloading terlama? | supported_with_caveat + HBAR |
| 9 | data_promo | PQ1 | Sell-In Des promo vs non-promo? | unsupported + Des scope note |
| 10 | multi | O11 | PTT tinggi + OOS tinggi — audit replenishment? | multi-agent or unsupported + suggested B06/customer gap |

## Pass criteria

- [ ] No free SQL executed.
- [ ] Sell-In/Out not summed as one revenue.
- [ ] Every response includes `chart_spec` block.
- [ ] Prescriptive rows state data limits (PQ1, O11).
- [ ] Indonesian saya/Anda when user asks in ID.

## Trace

Log `golden_questions.yaml` id when question matches catalog (e.g. `catalog_s01_gross_q4`).
