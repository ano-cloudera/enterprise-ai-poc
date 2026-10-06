# TEMPO local silver — domain map (Q4 2024: Oct–Dec)

This DuckDB instance holds **sample** rows mirroring on-prem **silver** table names. Numbers are for **local AI literacy testing**, not official management KPIs.

## Domains and tables

| Domain | Silver table | Business focus |
|--------|----------------|----------------|
| Sales / Sell-In | `silver.sales_oct_dec_2024` | Tempo billing / sell-in to customers by material, customer, sales office |
| B2B / Sell-Out | `silver.b2b_oct_dec_2024` | Partner sell-out, branch, PLU |
| Stock Tempo | `silver.stock_tempo_oct_dec_2024` | Warehouse stock by material and month |
| Service Level | `silver.service_level_oct_dec_2024` | PO vs DO quantities, fill rate by material |
| Picking | `silver.picking_okt_des_24` | Picking minutes and accuracy by sales office |
| Unloading | `silver.unloading_okt_des_24` | Unloading minutes by sales office |
| Stock SAT (Alfamart) | `silver.stock_sat_idm_monthly_okt_des_24` | DC vs store stock, division, PLU |
| SAT OOS | `silver.sat_oos_okt_des_2024` | Out-of-stock surveys by material / store |
| SAT Promo | `silver.sat_promo_des_24` | Promo observations (December-heavy scope) |

## Gold / governed concepts (context only — not all materialized locally)

When users ask for **company fill rate**, **material fill rate**, or **sales office SL**, compute from service level facts:

- Weighted fill rate ≈ `SUM(service_do_qty) / NULLIF(SUM(service_po_qty), 0)` aggregated at the grain asked (company, material, sales_off).

Sell-In value/qty live on sales tables; Sell-Out on B2B. **Do not invent joins** — inspect columns with `describe_table` first. Prefer single-table aggregates; cross-domain joins only when both keys exist in the sample.

## Scope boundaries

- Time: **2024-10 .. 2024-12** unless the table uses `bln` = OCT/NOV/DEC.
- No forecasting, no Jan 2025, no causal claims (“OOS caused sales drop”) unless the SQL result directly supports a descriptive correlation.
- Always state that results come from **local sample DuckDB**.
