# Optional Gold views (B2B branch×material, fill rate grain, promo B2B uplift)

DDL lives under `datasets/gold/`. Run each `CREATE VIEW` in Impala **after** upstream silver/gold dependencies exist, then refresh OSSIE (`backend/projects/tempo_scan_impala/ossie/tempo_core.ossie.yaml`) and redeploy backend.

## Ringkasan kelayakan

| Permintaan | Bisa dari data Q4? | View / metrik | Catatan |
|------------|-------------------|---------------|---------|
| **Sell-out per cabang × material** | **Ya** | `gold.corr_b2b_branch_material_month` + OSSIE `b2b_branch_material_*` | Baris `silver.b2b_oct_dec_2024` sudah punya `branch` + `c_0material`; view lama memisahkan grain. |
| **Fill rate dimensi tambahan** | **Sebagian** | `gold.corr_service_sales_office_material_month` **sudah ada** (office × material). Opsional: `corr_service_sales_office_cust_group_material_month` | `sales_off`+`material` sudah di OSSIE. `cust_grp3` di PoC sering **konstan** — view opsional hanya berguna jika di cluster kamu cardinality > 1. **Bukan** customer individual (beda dari Sales/B2B). |
| **Promo ROI langsung Alfamart** | **Tidak (ROI penuh)** | — | Tidak ada kolom **biaya/investasi promo** terstruktur; hanya teks `mekanisme`. |
| **Promo uplift channel B2B (Alfamart sell-out)** | **Ya (proxy)** | `gold.rpt_sat_promo_b2b_sellout_uplift` | Nov vs Des 2024 sell-out B2B untuk material yang sama dengan SAT Promo — **bukan ROI**, label sebagai uplift sell-out partner. |

## Deploy order

1. `01_corr_b2b_branch_material_month.sql`
2. `02_rpt_sat_promo_b2b_sellout_uplift.sql` (butuh `rpt_sat_promo_material_december_semantic` + B2B Nov/Des)
3. `03_corr_service_sales_office_cust_group_material_month.sql` (opsional — jalankan query cardinality di `datasets/audit/25_b2b_service_level_breakdown_investigation.sql` dulu)

Validasi:

```bash
.venv/bin/python scripts/validate_tempo_impala_contract.py --json
```

## OSSIE (sudah ditambahkan di repo)

- Dataset **`b2b_branch_material`** → metrik `b2b_branch_material_sell_out_value` / `quantity`
- Dataset **`sat_promo_b2b_sellout_uplift`** → metrik `promo_b2b_sellout_revenue_uplift` / `promo_b2b_sellout_volume_uplift` (routing: Alfamart/B2B/sell-out + uplift)
- Dataset **`service_level_sales_office_cust_group`** → metrik `sales_office_cust_group_service_fill_rate` (dimensi `cust_grp3` bila disebut di pertanyaan)
- Follow-up chat: drill DC/cabang → produk sell-out memakai metrik branch×material (bukan agregat nasional)

Setelah mengubah OSSIE, restart backend agar registry ter-load ulang sebelum uji FE.

## Yang tetap tidak bisa tanpa sumber data baru

- **ROI = (margin uplift − biaya promo)** di channel Alfamart
- Fill rate per **customer individual** (Service Level pakai **customer group**, bukan `0CUSTOMER` Sales)
- Baseline promo Alfamart multi-bulan sebelum Des 2024 di feed SAT Promo yang sama
