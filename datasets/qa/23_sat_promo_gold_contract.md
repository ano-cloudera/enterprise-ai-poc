# SAT Promo Gold Contract Evidence

**Evidence date:** 28 September 2026
**Environment:** Cloudera Workbench / Impala, supplied interactively by the user
**Physical observation source:** `silver.sat_promo_des_24`
**Existing material-list view:** `gold.corr_sat_promo_materials`

## Observed physical fields

The supplied Workbench result shows these source columns:

- `TGL_DCP` / `tgl_dcp`: observation timestamp; sample rows are on 3 December 2024.
- `cust_id`: observed customer/outlet identifier.
- `cust_code`: customer code at a different apparent cardinality from `cust_id`; no equivalence is assumed.
- `material_code`: observed product/material code.
- `Mekanisme` / `mekanisme`: raw promotion mechanism text, such as `POTONGAN 2.600` and `B2G1`.
- `program_status`: raw and unmapped code. Observed values are `Y`, `X`, and `T`; none is translated to active/inactive.

Contract rule: program_status is raw and unmapped until TEMPO supplies the controlled business definition.

## Reproduced status-profile result

The user executed the profiling query from the implementation discussion and supplied this visible result:

| Raw status | Total observations | Distinct materials | Distinct customer IDs | Distinct customer codes | Distinct mechanisms |
|---|---:|---:|---:|---:|---:|
| `Y` | 56,349 | 72 | 2,393 | not recorded; value obscured in screenshot | 50 |
| `X` | 10,758 | 74 | 797 | 38 | 49 |
| `T` | 730 | 63 | 418 | 32 | 45 |

The visible status counts total **67,837 source observations**. Distinct counts must not be summed across statuses because the same material, customer, or mechanism can occur in multiple status groups.

The follow-up Workbench audit confirmed the complete source profile:

- Total observations: **67,837**
- Distinct materials: **77**
- Distinct customer IDs: **2,437**
- Distinct customer codes: **55**
- Distinct mechanisms: **55**
- Minimum observation date: **2024-12-03**
- Maximum observation date: **2024-12-31**
- Null dates: **0**
- Null/blank materials: **0**
- Null/blank mechanisms: **0**
- Null/blank program statuses: **0**
- Month distribution: **67,837 rows in December 2024 only**

## Admission decision

| Check | Status | Evidence or required action |
|---|---|---|
| Required columns exist | PASS | Workbench table shows date, customer, material, mechanism, and status columns. |
| December 2024 period | PASS | Minimum 3 December, maximum 31 December; all 67,837 rows are in month 12 of 2024. |
| Raw status cardinality | PASS | `Y`, `X`, and `T` distribution recorded above. |
| Material cardinality | PASS | Per-status distinct counts recorded above. |
| Null/blank required fields | PASS | Date, material, mechanism, and program-status null/blank counts are all zero. |
| Full source date range | PASS | 3–31 December 2024 only. |
| Semantic-view deployment | PASS | `gold.rpt_sat_promo_material_december_semantic` returned 297 semantic rows. |
| Source reconciliation | PASS | `SUM(promo_observation_count)` returned 67,837, exactly matching the Silver source total. |
| Canonical grain uniqueness | PASS | Duplicate exact-grain rows: **0**. |
| Semantic invariants | PASS | Negative observation rows, outside-December rows, and null/blank material rows: **0** each. |

**Admission decision:** PASS. The Silver source contract, canonical semantic view, source reconciliation, exact-grain uniqueness, and semantic invariants all pass. The two governed SAT Promo metrics are admitted with the business caveats below.

## Business caveats

- `program_status` is raw and unmapped; the agent may report code distributions but may not call any code active, inactive, successful, or failed.
- `mekanisme` text is preserved as observed and has not received a TEMPO-controlled category dictionary.
- Row counts are field-audit observations, not unique promotions, products, customers, redemptions, or sales transactions.
- Promo cost, revenue attribution, uplift, and ROI are not provided by this contract.
