# Tempo: Jawaban Klarifikasi Data

**Untuk:** Tim Cloudera Enterprise AI PoC
**Dari:** Tim Tempo
**Tanggal:** September 2025
**Status:** 8 dari 10 pertanyaan terjawab. Pending: #4, #9.

**Dokumen terkait:**
- `TEMPO_DATA_UNDERSTANDING.md` — pemahaman data lengkap
- `TEMPO_DATAMART_ERD.png` — draft ERD untuk review Tempo

---

## 1. Scope PoC

**Pertanyaan:** Untuk PoC ini, domain/table mana saja yang perlu difokuskan? Apakah ada join key, metrik/KPI, dan formula resmi yang harus kami capai? Jika ada ERD atau diagram relasi bisnis dari sisi Tempo, mohon dishare (kami juga sudah punya draft ERD untuk direview).

**Jawaban Tempo:**

Semua table punya context bisnis masing-masing, dan beberapa data saling terkait misalnya kode material, kode customer dll. Kami tidak menyiapkan ERD, boleh di share understanding ERD nya untuk kami beri feedback.

**Follow-up kami (draft):** Table pada dasarnya independent per domain, tapi untuk PoC perlu relasi antar table. Join key yang kami identifikasi: **kode material**, **kode customer**, **lokasi** (+ periode). Detail & draft pesan: `TEMPO_KLARIFIKASI_FOLLOWUP.md` (#1).

---

## 2. Data Dictionary

**Pertanyaan:** Apakah tersedia data dictionary untuk file-file ini (definisi field, formula, contoh nilai)?

**Jawaban Tempo:**

Tidak ada.

---

## 3. Catatan terkait Data.xlsx

**Pertanyaan:** Di file catatan ada tulisan "data sales jan-mar 2026–2034". Apa maksudnya? Apakah ini typo, atau memang ada arti khusus?

**Jawaban Tempo:**

Catatan masih relevan untuk diterapkan ke data sales Oct-Dec 2024.

---

## 4. Custom Field Z*

**Pertanyaan:** Mohon definisi lengkap field custom (`Z*`), terutama yang belum ada di `Custom Key Figure Sales.xlsx`. Untuk kolom standard `0*`, kami asumsikan mengikuti standard SAP. Mohon dikoreksi jika ada yang berbeda.

**Jawaban Tempo:**

*(Belum dijawab)*

---

## 5. Stock

**Pertanyaan:** Apa beda `Stock*.txt` (Stock Tempo) vs `Stock SAT-IDM*.xlsb`? Mana yang dipakai untuk PoC?

**Jawaban Tempo:**

Stok Tempo adalah posisi stok di Gudang/Cabang milik Tempo. Sedangkan Stock SAT-IDM adalah stock produk Tempo di Dist.Center/Outlet milik Alfamart dan Indomaret.

---

## 6. SAT

**Pertanyaan:** Kenapa SAT Promo hanya Desember? Apakah data Okt–Nov bisa disediakan? Untuk SAT OOS yang harian, apakah boleh di-aggregate ke bulanan untuk join ke Sales?

**Jawaban Tempo:**

Data promo memang hanya ada December saja. Bebas untuk mengolah data yang kita berikan dengan fungsi aggregate dll.

---

## 7. Sales vs B2B

**Pertanyaan:** Kenapa Sales General dan B2B dipisah? Apakah datanya overlap atau benar-benar terpisah?

**Jawaban Tempo:**

Data Sales adalah data penjualan Tempo ke semua customer nya (Sell In). Data B2B adalah data penjualan Alfamart dan Indomaret ke end consumer (Sell Out).

**Catatan internal (Irvan, Sep 2025):**

Untuk poin ini, salah satu report yang bisa dibuat: **perbandingan volume barang keluar dari Tempo sebagai supplier ke jaringan distribusi (Sell In)** vs **jumlah produk yang benar-benar terjual oleh jaringan partner (Alfamart/Indomaret) ke end customer (Sell Out)**.

> Perlu diverifikasi dulu ke data aktual di file `Sales*.txt` dan `B2B *.txt` sebelum report ini dijadikan use case resmi PoC.

**Potensi use case Forecasting:**

Setelah data diverifikasi, perbandingan Sell In vs Sell Out ini bisa masuk **bagian forecasting PoC**, misalnya:

- Bandingkan trend volume **Sell In** (`Sales*.txt`) vs **Sell Out** (`B2B *.txt`) per material/bulan
- Identifikasi gap (barang sudah keluar dari Tempo tapi belum terjual di outlet, atau sebaliknya)
- Jadi sinyal untuk **forecast demand di channel modern trade** (Alfamart/Indomaret)
- Bisa dilengkapi data **Stock SAT-IDM** (stok di outlet) untuk konteks pipeline stok

*Status: usulan use case, pending verify data & scope forecasting PoC.*

---

## 8. Revenue Resmi

**Pertanyaan:** Kolom mana yang jadi official revenue figure: `BILL_VAL`, `Net Sales`/`VV802`, atau `DO Amount`/`DO_AMT`?

**Jawaban Tempo:**

Bisa pakai Bill Value (Gross Sales).

---

## 9. Key Figure ÷ 100

**Pertanyaan:** Apakah nilai key figure memang harus dibagi 100? Kolom mana saja, dan apakah berlaku untuk data Okt–Des 2024?

**Jawaban Tempo:**

Pak Gunawan bisa berikan konfirmasi.

*(Pending)*

---

## 10. Master Data Tambahan

**Pertanyaan:** Apakah ada master data lain (customer, material, plant, dll.) atau informasi tambahan yang bisa dilengkapi?

**Jawaban Tempo:**

Tidak ada.

---

## Ringkasan Implikasi untuk PoC

| Temuan | Implikasi |
|--------|-----------|
| Sales = Sell In, B2B = Sell Out | Jangan double-count revenue. Analisis terpisah. Usulan report & **forecasting use case**: bandingkan Sell In vs Sell Out (verify data dulu). |
| Stock Tempo vs SAT-IDM | Stok internal Tempo vs stok di outlet Alfamart/Indomaret. |
| Revenue = `BILL_VAL` | Official metric: Gross Sales via Bill Value. |
| Tidak ada data dictionary & master data | Dimension tetap kode. PoC fokus analisis numerik. |
| Catatan file relevan untuk Okt–Des 2024 | Terapkan aturan transformasi dari file catatan. |
| Aggregate SAT OOS OK | Boleh aggregate harian ke bulanan untuk join ke Sales. |
| ERD | Tempo belum punya ERD resmi. Review draft ERD dari tim Cloudera. |

---

## Pending Follow-up

| # | Item | PIC |
|---|------|-----|
| 4 | Definisi lengkap custom field `Z*` | Tim Tempo |
| 9 | Konfirmasi key figure ÷ 100 (kolom & periode) | Pak Gunawan |
| - | Review draft ERD | Tim Tempo |
| - | Mapping `0SALES_OFF` ↔ `BRANCH` ↔ `dcname` ↔ `Plant` | Tim Tempo |
| - | Enum Picking: `sStatus`, `Cycle`, `LP` | Tim Tempo |

---

## PoC interim defaults (F0b gate — untuk Agent Studio)

Digunakan **sampai** jawaban follow-up ([TEMPO_KLARIFIKASI_FOLLOWUP.md](TEMPO_KLARIFIKASI_FOLLOWUP.md)) diterima. Agent wajib menyebut asumsi ini di `assumptions[]`.

| # | Topik | Konfirmasi Tempo | Default PoC (agent + Gold) |
|---|--------|------------------|----------------------------|
| 1 | Revenue resmi | **#8:** `BILL_VAL` (Gross Sales) | Metric `gross_billing_value`; Gold sudah IDR |
| 2 | Sales vs B2B | **#7:** Sell-In vs Sell-Out terpisah | Jangan jumlahkan; bandingkan/rasio saja |
| 3 | Stock Tempo vs SAT-IDM | **#5:** gudang Tempo vs outlet partner | Domain terpisah; join via PLU/material + periode |
| 4 | SAT OOS aggregate | **#6:** boleh aggregate | Harian → bulan untuk join Sales |
| 5 | SAT Promo periode | **#6:** hanya Desember 2024 | Filter `calmonth=202412` untuk join Sales/B2B |
| 6 | Fill rate | Belum definisi resmi | `SUM(DO_QTY)/SUM(PO_QTY)` via metric `company_fill_rate` / `service_fill_rate` |
| 7 | OOS definisi | Belum definisi resmi | `Stok_akhir = 0` = OOS (exploratory, bukan governed) |
| 8 | Amount ÷100 raw export | **#9 pending** Pak Gunawan | **Gold semantic views sudah normalisasi** — agent: *never multiply by 100 again* |
| 9 | Lokasi cross-domain | Follow-up open | **Tidak** auto-equate `0SALES_OFF`, `BRANCH`, `dcname`, `Plant` |
| 10 | Scope waktu | Implisit Q4 2024 | Okt–Des 2024 only; promo Des-only |

**Dispatch:** kirim slide follow-up ke Tempo; lacak jawaban di tabel di atas (update [TEMPO_KAMUS_DATA_AI.md](TEMPO_KAMUS_DATA_AI.md) §6).
