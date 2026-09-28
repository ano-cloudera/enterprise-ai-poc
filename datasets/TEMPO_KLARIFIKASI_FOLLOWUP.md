# Tempo PoC: Follow-up Questions (Copy-paste ke Slide)

**Untuk:** Tim Tempo / Pak Gunawan
**Dari:** Tim Cloudera Enterprise AI PoC
**Referensi:** Jawaban klarifikasi awal (`TEMPO_KLARIFIKASI_JAWABAN.md`)

---

## SLIDE 1: Follow-up Questions

### Konteks

- Setiap domain/table punya context bisnis sendiri, secara prinsip bisa **independent**
- Untuk PoC, kami perlu bisa **relate antar table** jika butuh informasi tambahan
- Contoh use case: Sell In vs Sell Out, stok vs penjualan, OOS vs penjualan
- Di **Catatan terkait Data.xlsx** ada catatan: angka di export SAP perlu **dibagi 100** (Tempo konfirmasi masih berlaku Okt-Des 2024)

### Join key yang kami identifikasi

| Join key | Field di data | File / domain |
|----------|---------------|---------------|
| Kode material | `0MATERIAL`, `Material_code`, `PLU` | Sales, B2B, Stock, Service Level, SAT |
| Kode customer | `0CUSTOMER`, `Cust Id`, `cust_id` | Sales, B2B, Picking, SAT |
| Lokasi (sales) | `0SALES_OFF`, `sales_office` | Sales, B2B, Service Level, Picking, Unloading |
| Lokasi (stok) | `Plant`, `0STOR_LOC` | Stock Tempo (ST1-ST3) |
| Periode | `0CALMONTH`, `TGL_DCP` | Semua domain transaksi |

### Pemetaan lokasi per domain

| Domain | Field lokasi | Arti |
|--------|--------------|------|
| Sales, B2B, Service Level, Logistics | `0SALES_OFF` / `sales_office` | Cabang/area penjualan |
| Stock Tempo | `Plant` + `0STOR_LOC` | Gudang fisik + lokasi penyimpanan |
| SAT | Tidak ada field lokasi | Join via customer + material + periode |

### Use case join PoC

| Use case | File | Join key (asumsi kami) |
|----------|------|------------------------|
| Sell In vs Sell Out | Sales ↔ B2B | material + customer + cabang + bulan |
| Sales vs Service Level | Sales ↔ Service Level | material + cabang + bulan |
| Sales vs Stock | Sales ↔ Stock | material + bulan |
| Sales vs OOS | Sales ↔ SAT OOS | customer + material + bulan |

### Custom field Z* — konteks

- Field `Z*` = kolom **custom Tempo** di SAP (kebanyakan **angka/metrik**, bukan flag ya/tidak)
- File reference (`Custom Key Figure Sales.xlsx`) hanya cover **9 field Sales**
- Tidak ada data dictionary resmi dari Tempo

### Inventaris field Z*

| File | Field Z* | Ada definisi? |
|------|----------|---------------|
| `Sales*.txt` (6 file) | ZCOST, ZIOKF0028-0033, ZIOCH0042, ZDIS_D8, ZSUBHUB (~10 field) | Sebagian (9 field di R2) |
| `Service Level Oct - Dec 2024.txt` | ZIOKF0034-0069 (~34 field) | **Tidak ada** |
| B2B, Stock, Logistics, SAT | Tidak ada field Z* | - |

### Definisi Sales yang sudah ada (dari Custom Key Figure Sales.xlsx)

| Kode | Deskripsi |
|------|-----------|
| ZIOKF0028 | Cash Discount Sales |
| ZIOKF0029 | Cash Discount Return |
| ZIOKF0030 | Disc. Principal F1 |
| ZIOKF0031 | Disc. F5 Add Hoc |
| ZIOKF0032 | Disc. Inv Volume |
| ZIOKF0033 | Disc. CN Volume |
| ZIOCH0042 | Customer Number (Sales View) |
| ZCOST | COGS Value |

**Belum ada definisi:** ZDIS_D8, ZSUBHUB (Sales) dan seluruh ZIOKF0034-0069 (Service Level)

---

### Pertanyaan follow-up

**Relasi antar data**

1. Apakah join key kami sudah benar **per use case**? (bukan selalu ke-4 key sekaligus)

   | Use case | Join key yang kami pakai | Contoh |
   |----------|--------------------------|--------|
   | Sell-In vs Sell-Out | `0MATERIAL` + `0CUSTOMER` + `0SALES_OFF` + `0CALMONTH` | Material `12345`, customer `C001`, cabang `JKT01`, bulan `202411` |
   | Sales vs Service Level | `0MATERIAL` + `0SALES_OFF` + `0CALMONTH` | Material `12345`, cabang `JKT01`, bulan `202411` |
   | Sales vs Stock Tempo | `0MATERIAL` + `0CALMONTH` | Material `12345`, bulan `202411` |
   | Sales vs SAT OOS | `0CUSTOMER` + `0MATERIAL` + periode | Customer `C001`, material `12345`, survey date |

   → Apakah mapping ini benar? Ada **composite key tambahan** (mis. `0SALESORG + 0SALES_OFF`)?

2. Apakah `0SALES_OFF` / `sales_office` memang **cabang penjualan**?
   > Contoh: di file Sales Okt 2024, kode `JKT01` = cabang Jakarta?

3. Apakah data **Sales** dan **Service Level** biasanya **dianalisis bersama** di management? Jika ya, join-nya pakai key apa?
   > Contoh: *"Fill Rate material X di cabang Y bulan November"* — join cukup `material + cabang + bulan`?

4. Di data **Stock Tempo**, field **Plant** dan **Storage Location** maksudnya apa? (gudang fisik? area di dalam gudang?)
   > Contoh: Plant `1000` = gudang Cibitung? `0STOR_LOC` `0001` = area di dalam gudang?

5. Apakah data **stok** biasanya **dianalisis bersama penjualan (Sales)**? Jika ya, bagaimana biasanya dihubungkan?
   > Contoh: *"Stok material X vs penjualan bulan November"* — join cukup `material + bulan`, atau perlu `Plant` juga?

**Custom field Z***

6. Apa **definisi logic/bisnis** masing-masing field Z* di Sales dan Service Level?
7. **Analisis apa** yang biasa dibuat dari field Z* ini? Contoh:
   - Total **diskon** per cabang / per produk / per bulan (ZIOKF0028-0033)
   - **Gross margin**: penjualan minus COGS (BILL_VAL vs ZCOST)
   - **Discount leakage**: cabang/produk mana diskon-nya paling besar
   - **Komponen service level** per cabang (ZIOKF0034-0069)
   - Apakah ada analisis lain yang biasa dipakai management?
8. Apakah inventaris Z* di atas **sudah lengkap**? Ada Z* di file lain?
9. Apa definisi **ZDIS_D8** dan **ZSUBHUB** (Sales, belum ada di file reference)?
10. Apa definisi **ZIOKF0034-0069** (Service Level, ~34 field, belum ada di file reference)?
11. Field Z* mana yang **masih aktif dipakai** vs sudah tidak relevan?

**Aturan ÷ 100 (Pak Gunawan, dari Catatan terkait Data.xlsx)**

**Konteks — kenapa kami tanya:**
Di file **Catatan terkait Data.xlsx** ada catatan bahwa angka di export SAP perlu **dibagi 100**. Kami perlu konfirmasi supaya angka di PoC (diskon, COGS, margin, dll.) tidak salah skala.

**Asumsi kami saat ini (tolong dikoreksi):**
- Aturan ini kemungkinan terkait **format export SAP** (angka disimpan tanpa desimal, jadi perlu ÷100), bukan aturan insentif bisnis — tapi belum pasti.
- Yang *kemungkinan* kena: kolom custom `Z*` (`ZIOKF0028–0033`, `ZCOST`) dan `DIS_*` di **Sales**.
- Yang *kemungkinan* **tidak** kena: `BILL_VAL`, `DO_AMT`, `PO_QTY`, `DO_QTY` (key figure standar) — karena di Gold Impala sudah terlihat dinormalisasi.
- Belum jelas apakah **Service Level** (`ZIOKF0034–0069`, `PO_AMT`, `DO_AMT`, dll.) juga perlu ÷100.

**Contoh supaya jelas maksud kami:**

| Kolom | Nilai mentah di file TXT | Setelah ÷100 (jika benar) | Pertanyaan kami |
|-------|--------------------------|---------------------------|-----------------|
| `ZIOKF0028` (Cash Discount) | `150000` | `1,500` IDR? | Apakah memang harus ÷100? |
| `ZCOST` (COGS) | `8500000` | `85,000` IDR? | Sama? |
| `BILL_VAL` | `125000000` | Sudah benar / tidak perlu ÷100? | Konfirmasi |
| `ZIOKF0034` (Service Level) | `9800` | `98`? | Service Level juga kena? |

**Pertanyaan follow-up (format jawaban yang kami harapkan):**

12. **Apakah aturan ÷100 memang berlaku?** Untuk periode **Okt–Des 2024**?
    > Jawaban yang kami harapkan: **Ya/Tidak** + apakah berlaku untuk semua file export SAP di periode itu.

13. **Kolom/file mana saja yang perlu ÷100?**
    > Jawaban yang kami harapkan: **daftar kolom eksplisit** per file, misalnya:
    > - `Sales*.txt` → `ZIOKF0028`, `ZIOKF0029`, …, `ZCOST`, `DIS_A`, `DISCD12` — **ya, ÷100**
    > - `Sales*.txt` → `BILL_VAL`, `DO_AMT` — **tidak perlu**
    > - `Service Level*.txt` → `ZIOKF0034–0069` — **ya/tidak?**
    > - `B2B`, `Stock`, `Logistics`, `SAT` — **tidak ada / tidak perlu**

14. **Scope kolom — apakah cuma Z* & DIS_* di Sales, atau lebih luas?**
    > Jawaban yang kami harapkan: centang jelas:
    > - [ ] Hanya kolom `Z*` (ZIOKF, ZCOST, ZIOCH, ZDIS, ZSUBHUB) di Sales
    > - [ ] Semua kolom `DIS_*` di Sales
    > - [ ] Key figure standar (`BILL_VAL`, `DO_AMT`, `CN_QTY`, dll.) — **juga perlu?**
    > - [ ] Service Level (`ZIOKF0034–0069`, `PO_AMT`, `DO_AMT`, dll.)
    > - [ ] File/domain lain?

15. **Catatan ÷100 ini soal apa?**
    > Jawaban yang kami harapkan: pilih salah satu (atau jelaskan):
    > - **A)** Cara export angka dari SAP (technical — angka disimpan ×100 tanpa desimal)
    > - **B)** Aturan bisnis / insentif (angka harus diskalakan untuk perhitungan tertentu)
    > - **C)** Keduanya / kondisi lain: ___
    >
    > *Kalau A:* kami terapkan sebagai transform rule saat load data.
    > *Kalau B:* kami catat sebagai business rule di semantic layer, bukan auto-transform.

---

## TEKS CHAT (Copy-paste)

```
Follow-up klarifikasi data (poin #1, #4, #9):

A) Relasi antar data:
1) Join key kami sudah benar per use case? (bukan selalu ke-4 key sekaligus)
   - Sell-In vs Sell-Out: 0MATERIAL + 0CUSTOMER + 0SALES_OFF + 0CALMONTH
     (contoh: material 12345, customer C001, cabang JKT01, bulan 202411)
   - Sales vs Service Level: 0MATERIAL + 0SALES_OFF + 0CALMONTH
     (contoh: material 12345, cabang JKT01, bulan 202411)
   - Sales vs Stock: 0MATERIAL + 0CALMONTH
     (contoh: material 12345, bulan 202411)
   - Sales vs SAT OOS: 0CUSTOMER + 0MATERIAL + periode
   → Mapping ini benar? Ada composite key tambahan (mis. 0SALESORG + 0SALES_OFF)?

2) 0SALES_OFF / sales_office = cabang penjualan?
   (contoh: kode JKT01 di Sales Okt 2024 = cabang Jakarta?)

3) Sales & Service Level biasanya dianalisis bersama? Join pakai key apa?
   (contoh: "Fill Rate material X di cabang Y bulan Nov" → material + cabang + bulan?)

4) Di Stock Tempo, Plant & Storage Location maksudnya apa?
   (contoh: Plant 1000 = gudang Cibitung? 0STOR_LOC 0001 = area di dalam gudang?)

5) Stok & penjualan biasanya dianalisis bersama? Bagaimana dihubungkan?
   (contoh: stok material X vs penjualan Nov → cukup material + bulan, atau perlu Plant?)

B) Custom field Z*:
6) Definisi logic/bisnis masing-masing field Z* di Sales & Service Level?
7) Analisis apa yang biasa dibuat? Contoh: total diskon, gross margin,
   discount leakage, komponen service level. Ada analisis lain?
8) Inventaris Z* kami sudah lengkap?
9) Definisi ZDIS_D8 & ZSUBHUB (Sales)?
10) Definisi ZIOKF0034-0069 (Service Level)?
11) Field Z* mana yang masih aktif dipakai?

C) Aturan ÷ 100 (Pak Gunawan — dari Catatan terkait Data.xlsx):

Konteks: di file catatan ada aturan angka export SAP perlu ÷100.
Kami perlu konfirmasi supaya diskon, COGS, margin tidak salah skala.

Contoh maksud kami:
- ZIOKF0028 = 150000 di file → jadi 1,500 IDR setelah ÷100?
- ZCOST = 8500000 → jadi 85,000 IDR?
- BILL_VAL = 125000000 → sudah benar / tidak perlu ÷100?

12) Aturan ÷100 berlaku? Untuk Okt-Des 2024 semua file SAP?
    → Jawaban: Ya/Tidak + scope periode

13) Kolom/file mana saja yang perlu ÷100?
    → Jawaban: daftar kolom eksplisit per file
    (mis. Sales: ZIOKF0028-0033, ZCOST, DIS_* = ya;
     BILL_VAL, DO_AMT = tidak; Service Level ZIOKF0034-0069 = ?)

14) Scope — centang yang benar:
    [ ] Z* di Sales saja
    [ ] DIS_* di Sales
    [ ] Key figure standar (BILL_VAL, DO_AMT, dll.) juga?
    [ ] Service Level (ZIOKF0034-0069, PO_AMT, DO_AMT)?
    [ ] File lain (B2B, Stock, SAT)?

15) Catatan ÷100 soal apa?
    A) Cara export SAP (technical, angka ×100 tanpa desimal)
    B) Aturan bisnis/insentif
    C) Lainnya: ___

Terima kasih.
```

---

## Catatan internal (jangan taruh di slide)

| Item | PIC | Status |
|------|-----|--------|
| Konfirmasi relasi & Z* | Tim Tempo | Pending |
| Konfirmasi ÷ 100 | Pak Gunawan | Pending |

**Catatan ÷ 100 untuk presenter:**
- Jelaskan dulu *kenapa* kita tanya: supaya angka diskon/COGS/margin tidak off 100×.
- Minta jawaban **spesifik per kolom**, bukan "ya semua" atau "tidak semua".
- Gold Impala sudah dinormalisasi — pertanyaan ini mainly untuk validasi raw export + dokumentasi semantic rule.
- Jika jawaban = technical export (A), kita apply transform. Jika bisnis (B), kita catat di governance, tidak auto-transform.
