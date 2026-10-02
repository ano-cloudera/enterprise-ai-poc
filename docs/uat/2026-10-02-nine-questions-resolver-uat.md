# UAT — 9 pertanyaan dry-run (resolver + governed SQL), backend-v2 lokal

**Run date:** 2026-10-02  
**Lingkungan:** `enterprise-ai-poc` / `backend-v2`, working tree dengan perbaikan cabang fill-rate (#8)  
**Metode:** `SemanticContextService.resolve()` → `compile_governed()` bila `status=resolved` tanpa `dimension_mismatch` → `validate_sql()`  
**Tidak dijalankan di run ini:** pipeline penuh `ChatService` (Qwen/GPT + Impala live). Untuk jawaban verbatim + angka live, ulangi di CAI seperti [2026-10-01-qwen-uat.md](2026-10-01-qwen-uat.md).

## Ringkasan vs run 2026-10-01 (Qwen + Impala live)

| # | Pertanyaan (singkat) | 2026-10-01 (live) | 2026-10-02 (resolver) | Catatan |
|---|---|---|---|---|
| 01 | Top 10 produk penjualan Tempo | SUCCESS · governed | **CLARIFICATION** · sales_stage | Sell-In vs Sell-Out; jawab **Sell-In** untuk lanjut ke `material_sell_in_value` |
| 02 | Top 10 cabang / sales office | SUCCESS · sql_fallback | **RESOLVED · governed** | `sales_office_material_sell_in_value` · `gold.rpt_sap_sales_office_material_month_semantic` |
| 03 | Stok produk A cabang A + cover hari | NO_DATA · governed | **RESOLVED + mismatch `branch`** | Planner/ hint; metric `months_of_stock_cover` tidak punya dimensi cabang |
| 04 | Top 10 produk B2B | SUCCESS · governed | **RESOLVED · governed** | `material_sell_out_value` (SAP material sell-out, bukan PLU B2B branch) |
| 05 | Top 10 DC Alfamart penjualan | CLARIFICATION | **CLARIFICATION** · sales_stage | Sama: perlu pilih Sell-In vs Sell-Out |
| 06 | Stok produk A toko vs DC | CLARIFICATION | **CLARIFICATION** · sat_idm | Pilih DC stock qty vs store stock qty |
| 07 | Promo ROI + rekomendasi | CLARIFICATION | **CLARIFICATION** · promo_roi_proxy | Proxy uplift GT (bukan ROI langsung) |
| 08 | SL / fill rate cabang, urut terjelek | SUCCESS · governed (salah grain live lama) | **RESOLVED · governed** | **`sales_office_service_fill_rate`** · `ORDER BY metric_value ASC` |
| 09 | Unloading + picking vs industri | SUCCESS · sql_fallback | **FALLBACK** · multi_concept | Perlu LLM planner (`sql_fallback`) |

**Legenda status resolver:** `needs_clarification` → UI CLARIFICATION; `resolved` + SQL valid → path governed jika planner tidak override; `resolved` + `dimension_mismatch` → biasanya `sql_fallback` + `resolver_hint`; `fallback` → `sql_fallback`.

---

## Detail per pertanyaan

### 01 — Top 10 produk dengan penjualan terbesar di Tempo

- **Resolver:** `needs_clarification` (`reason=sales_stage`)
- **Expected UI strategy:** `clarification`
- **Pertanyaan klarifikasi:** Sell-In (Tempo ke customer) vs Sell-Out (partner ke konsumen)?
- **Setelah user pilih Sell-In:** gunakan metric `gross_billing_value` / `material_sell_in_value` (sama pola run 1 Oct setelah klarifikasi implisit atau alias sell-in).
- **Perbandingan 1 Oct:** live langsung SUCCESS governed — selisih karena ambiguitas `penjualan` + `di Tempo` sekarang memicu klarifikasi deterministik.

---

### 02 — Top 10 cabang/ sales office dengan penjualan terbesar di tempo

- **Resolver:** `resolved`
- **Metric:** `sales_office_material_sell_in_value`
- **Dimensions:** (default agregat per sales office)
- **SQL valid:** yes
- **Strategy (setelah deploy):** `governed`

```sql
SELECT
  d.sales_office AS sales_office,
  SUM(d.sell_in_bill_val) AS metric_value
FROM gold.rpt_sap_sales_office_material_month_semantic d
WHERE d.calmonth BETWEEN 202410 AND 202412
GROUP BY d.sales_office
ORDER BY metric_value DESC
LIMIT 10
```

- **Perbandingan 1 Oct:** dulu `sql_fallback`; sekarang governed langsung (perbaikan dimensi cabang / sales office).

---

### 03 — Tampilkan stok produk A di cabang A dan hitung bisa meng-cover penjualan berapa hari dari stok tersebut

- **Resolver:** `resolved`
- **Metric:** `months_of_stock_cover`
- **Dimensions:** `["material"]`
- **Dimension mismatch:** `["branch"]` — permintaan “cabang A” tidak didukung grain metric ini
- **Expected strategy:** `sql_fallback` (LLM + `resolver_hint`), bukan governed murni
- **SQL kandidat (jika dimensi cabang diabaikan):** agregat per `material` saja — tidak memenuhi “cabang A”

- **Perbandingan 1 Oct:** NO_DATA governed (placeholder produk/cabang); gap data cabang + stock cover masih real.

---

### 04 — Top 10 produk di B2B dengan penjualan tertinggi

- **Resolver:** `resolved`
- **Metric:** `material_sell_out_value`
- **SQL valid:** yes
- **Strategy:** `governed`

```sql
SELECT
  d.material AS material,
  SUM(d.sell_out_bill_val) AS metric_value
FROM gold.rpt_sap_material_month_semantic d
WHERE d.has_sell_out = TRUE
  AND d.calmonth BETWEEN 202410 AND 202412
GROUP BY d.material
ORDER BY metric_value DESC
LIMIT 10
```

- **Caveat:** pertanyaan menyebut “B2B”; resolver memilih sell-out material SAP, bukan `b2b_*` PLU/branch. Sesuai run 1 Oct.

---

### 05 — Top 10 DC Alfamart dengan penjualan tertinggi

- **Resolver:** `needs_clarification` (`sales_stage`)
- **Expected strategy:** `clarification`
- **Catatan:** “DC Alfamart” + “penjualan” belum cukup spesifik sell-in DC stock vs sell-out; sama seperti 1 Oct.

---

### 06 — Cek stok produk A di toko alfamart dan bandingkan dengan stok di DC

- **Resolver:** `needs_clarification` (`sat_idm_stock_level_comparison`)
- **Options:** `sat_dc_stock_quantity` vs `sat_store_stock_quantity`
- **Expected strategy:** `clarification` (dua query terpisah by design)

---

### 07 — Hitung promo dengan ROI terbaik dan berikan rekomendasi/ saran

- **Resolver:** `needs_clarification` (`promo_roi_proxy_choice`)
- **Expected strategy:** `clarification` — tidak ada ROI promo langsung; pilih proxy uplift (revenue / volume / margin)

---

### 08 — Hitung service level/ fill rate di cabang tempo dan urutkan SL terjelek

- **Resolver:** `resolved`
- **Metric:** `sales_office_service_fill_rate`
- **Dimensions:** `["sales_off"]`
- **SQL valid:** yes
- **Strategy:** `governed` (ini perbaikan utama 2 Oct — **bukan** `company_fill_rate`)

```sql
SELECT
  d.sales_off AS sales_off,
  SUM(d.service_do_qty) / NULLIF(SUM(d.service_po_qty), 0) AS metric_value
FROM gold.corr_service_sales_office_material_month d
WHERE d.calmonth BETWEEN 202410 AND 202412
GROUP BY d.sales_off
ORDER BY metric_value ASC
LIMIT 50
```

- **Perbandingan live sebelum redeploy:** KPI ~0,777 company-wide = routing lama; setelah redeploy harus bar chart / tabel per `sales_off`, SL terburuk di atas (ASC).
- **Local Agent:** opsional (`LOCAL_AGENT_BASE_URL`); tidak wajib jika governed path sudah deploy.

---

### 09 — Analisa data unloading dan picking dan berikan Analisa dan perbandingan dengan Industri standard

- **Resolver:** `fallback` (`reason=multi_concept_metric_mismatch`)
- **Expected strategy:** `sql_fallback` — dua domain (picking + unloading), tidak satu metric tunggal
- **Perbandingan 1 Oct:** SUCCESS sql_fallback; perilaku resolver konsisten.

---

## Checklist verifikasi live (CAI, setelah redeploy)

1. **#08** — Footer chat: `strategy=governed`, SQL/view `corr_service_sales_office_material_month`, bukan KPI tunggal 0,777.
2. **#02** — `strategy=governed`, top 10 `sales_office`, bukan planner fallback.
3. **#01** — Jika ingin tanpa klarifikasi: user jawab Sell-In atau ubah wording (“sell-in top 10 material”); evaluasi product apakah #01 harus auto Sell-In untuk “produk … di Tempo”.
4. **Impala** — `klist` valid di mesin uji; jalankan ulang pipeline penuh dan salin jawaban ke `docs/uat/2026-10-02-qwen-uat-live.md` (belum dibuat — menunggu run CAI).

## Repro lokal

```bash
cd backend-v2
../.venv/bin/python -m pytest tests/ -q
# Resolver snapshot: lihat commit script di git history atau ulangi resolve() per pertanyaan di atas.
```

**Tests terkait:** `test_uat_branch_service_level_ranking_resolves_sales_office_fill_rate`, `test_cabang_dimension_hint_does_not_produce_a_false_dimension_mismatch` (termasuk pertanyaan #2).
