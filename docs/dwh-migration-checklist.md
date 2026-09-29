# Checklist Migrasi Data Warehouse — Impala/Iceberg (S3 AWS → HDFS Private Cloud)

Konteks: migrasi cluster penuh, dari Cloudera di AWS (data fisik tersimpan di
S3, tabel format Iceberg) ke Cloudera Private Cloud on-prem (storage HDFS
klasik). Kedua environment sudah terhubung VPN. Tujuan: migrasi seminimal
mungkin usaha, dengan setiap langkah bisa diverifikasi sebelum lanjut ke
langkah berikutnya.

## Kenapa ini lebih ringan dari kelihatannya

Semua objek Gold layer yang dipakai project ini adalah `CREATE VIEW`, bukan
`CREATE TABLE` — sudah dikonfirmasi dengan mengecek semua 44 statement
`CREATE VIEW`/`CREATE TABLE` di `datasets/audit/*.sql` dan
`datasets/gold/*.sql` (hasilnya: 44 view, 0 tabel). Artinya **cuma 9 tabel
silver yang butuh transfer data fisik** — semua Gold view tinggal
di-`CREATE VIEW` ulang dari SQL yang sudah ditulis dan sudah divalidasi di
repo ini, bukan proses copy data.

## Daftar 9 tabel silver yang perlu dipindah

```text
silver.b2b_oct_dec_2024
silver.picking_okt_des_24
silver.sales_oct_dec_2024
silver.sat_oos_okt_des_2024
silver.sat_promo_des_24
silver.service_level_oct_dec_2024
silver.stock_sat_idm_monthly_okt_des_24
silver.stock_tempo_oct_dec_2024
silver.unloading_okt_des_24
```

---

## Langkah 1 — Pindahkan data fisik dari S3 (AWS) ke HDFS (Private Cloud)

Ini satu-satunya langkah yang benar-benar transfer data byte demi byte.
Karena source-nya S3 (Iceberg di atas S3) dan tujuan HDFS klasik, ini **bukan
sekadar "re-register metadata"** seperti kalau storage-nya sama — harus benar-
benar dipindah fisik filenya, karena S3 dan HDFS adalah dua filesystem yang
beda sepenuhnya.

### 1.1 — Cek dulu lokasi fisik file tiap tabel Iceberg di S3

Sebelum copy apa pun, cari tahu path S3 sesungguhnya untuk tiap tabel.
Jalankan di Impala/Hive lama (source, AWS):

```sql
DESCRIBE FORMATTED silver.sales_oct_dec_2024;
```

Cari baris `Location` di hasilnya — formatnya biasanya seperti:

```text
s3a://nama-bucket-anda/warehouse/silver.db/sales_oct_dec_2024
```

Catat path ini untuk **semua 9 tabel** sebelum lanjut. Iceberg table juga
punya folder `metadata/` di lokasi yang sama — folder ini WAJIB ikut
ter-copy, bukan cuma folder `data/`.

**Catatan soal path tujuan di HDFS**: contoh path tujuan
(`hdfs:///warehouse/silver.db/...`) di seluruh dokumen ini adalah **pola umum
saja, bukan path yang sudah dipastikan benar** untuk cluster Private Cloud
tujuan. Dicek langsung lewat Hue File Browser di `/user/partner-multipolar/`
pada cluster baru: baru ada folder `tempo-scan-poc/` di HDFS home directory
user, belum ada struktur warehouse `silver.db`/`gold.db` apa pun. Sebelum
menjalankan `distcp` di langkah 1.3, cek dulu ke admin/Cloudera Manager
cluster baru: (a) di path HDFS mana database Hive/Impala eksternal akan
disimpan (biasanya sesuatu seperti
`/warehouse/tablespace/external/hive/silver.db/` di CDP versi modern, bukan
`/warehouse/silver.db/` polos — beda dari satu instalasi CDP ke instalasi
lain), dan (b) apakah database `silver`/`gold` itu sendiri sudah dibuat
(`CREATE DATABASE IF NOT EXISTS silver;`) sebelum tabel-tabelnya didaftarkan.

### 1.2 — Cek akses `distcp` dari cluster tujuan ke S3

Dari node di cluster Private Cloud (yang akan menjalankan job `distcp`), pastikan kredensial AWS (access key/secret, atau role-based access kalau pakai IAM) sudah dikonfigurasi supaya Hadoop bisa baca `s3a://`. Test dulu dengan list sederhana sebelum copy besar:

```bash
hadoop fs -ls s3a://nama-bucket-anda/warehouse/silver.db/sales_oct_dec_2024/
```

Kalau ini gagal (access denied, credential error), **jangan lanjut ke distcp** — perbaiki dulu akses S3-nya. Ini kemungkinan besar butuh koordinasi dengan tim yang pegang kredensial AWS S3 sumber.

### 1.3 — Jalankan `distcp` per tabel, mulai dari yang paling kecil

Mulai dari tabel yang paling ringan sebagai uji coba (SAT Promo, cakupannya cuma Desember 2024 — kemungkinan besar volume-nya paling kecil dari 9 tabel):

```bash
hadoop distcp \
  -update \
  -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/sat_promo_des_24 \
  hdfs:///warehouse/silver.db/sat_promo_des_24
```

Penjelasan flag:

- `-update` — cuma copy file yang belum ada/berubah di tujuan (aman dijalankan ulang kalau terputus di tengah jalan)
- `-delete` — hapus file di tujuan yang sudah tidak ada di source (jaga konsistensi, pakai hati-hati kalau tujuan sudah pernah diisi sebagian dari proses lain)

Setelah tabel pertama ini berhasil dan diverifikasi (lihat 1.4), baru lanjut ke 8 tabel sisanya satu per satu — jangan copy semua sekaligus di percobaan pertama, supaya kalau ada masalah kredensial/jaringan, dampaknya cuma ke 1 tabel kecil dulu.

```bash
hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/b2b_oct_dec_2024 \
  hdfs:///warehouse/silver.db/b2b_oct_dec_2024

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/picking_okt_des_24 \
  hdfs:///warehouse/silver.db/picking_okt_des_24

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/sales_oct_dec_2024 \
  hdfs:///warehouse/silver.db/sales_oct_dec_2024

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/sat_oos_okt_des_2024 \
  hdfs:///warehouse/silver.db/sat_oos_okt_des_2024

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/service_level_oct_dec_2024 \
  hdfs:///warehouse/silver.db/service_level_oct_dec_2024

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/stock_sat_idm_monthly_okt_des_24 \
  hdfs:///warehouse/silver.db/stock_sat_idm_monthly_okt_des_24

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/stock_tempo_oct_dec_2024 \
  hdfs:///warehouse/silver.db/stock_tempo_oct_dec_2024

hadoop distcp -update -delete \
  s3a://nama-bucket-anda/warehouse/silver.db/unloading_okt_des_24 \
  hdfs:///warehouse/silver.db/unloading_okt_des_24
```

Ganti `nama-bucket-anda` dan path `warehouse/silver.db/...` sesuai hasil `DESCRIBE FORMATTED` di langkah 1.1 — jangan asumsikan strukturnya persis seperti contoh ini tanpa dicek dulu.

### 1.4 — Daftarkan tabel Iceberg di katalog Impala baru

Setelah file sudah pindah ke HDFS, tabel Iceberg-nya perlu didaftarkan ke
katalog (Hive Metastore) cluster baru supaya Impala baru bisa melihatnya.
Karena file metadata Iceberg (`metadata/*.metadata.json`) sudah ikut ter-copy
di langkah 1.3, biasanya cukup:

```sql
-- Di Impala cluster BARU
CREATE TABLE silver.sat_promo_des_24
  ...
LOCATION 'hdfs:///warehouse/silver.db/sat_promo_des_24'
TBLPROPERTIES ('table_type'='ICEBERG', 'metadata_location'='hdfs:///warehouse/silver.db/sat_promo_des_24/metadata/<file-metadata-terbaru>.metadata.json');
```

Cara paling aman menentukan file metadata terbaru: lihat isi folder
`metadata/` yang sudah ter-copy, cari file `.metadata.json` dengan nomor
urut/timestamp paling besar (Iceberg menomori tiap versi metadata secara
berurutan, misal `00001-....metadata.json`, `00002-....metadata.json`, dst —
pakai yang angkanya paling besar).

Kalau versi Impala di cluster baru mendukung `CREATE TABLE ... LIKE ICEBERG`
dari lokasi langsung (tanpa perlu tulis definisi kolom manual), pakai itu
karena jauh lebih sederhana dan tidak rawan salah ketik skema — cek dokumentasi versi Impala yang dipakai cluster baru untuk sintaks pastinya, karena ini bisa berbeda antar versi CDP.

### 1.5 — Verifikasi row count SETIAP tabel sebelum lanjut

Ini langkah wajib, jangan dilewati. Untuk tiap 1 dari 9 tabel:

```sql
-- Di Impala LAMA (AWS)
SELECT COUNT(*) FROM silver.sales_oct_dec_2024;

-- Di Impala BARU (Private Cloud), setelah didaftarkan
SELECT COUNT(*) FROM silver.sales_oct_dec_2024;
```

Kedua angka **harus identik**. Kalau tidak sama:
- Jangan lanjut ke tabel berikutnya atau ke Langkah 2.
- Cek dulu apakah `distcp` benar-benar selesai tanpa error (lihat log job MapReduce/YARN-nya, cari baris yang menyebut jumlah file gagal/skipped).
- Kemungkinan penyebab lain: file metadata Iceberg yang didaftarkan di Impala baru bukan versi metadata terbaru (lihat catatan di 1.4).

Ulangi verifikasi ini untuk **semua 9 tabel** satu per satu sebelum menyatakan Langkah 1 selesai.

---

## Langkah 2 — Jalankan ulang semua `CREATE VIEW` Gold, sesuai urutan

Sumber SQL-nya, urutan berdasarkan riwayat pembangunannya (baca komentar di
tiap file untuk pastikan dependency-nya, karena view yang lebih baru kadang
merujuk ke view yang lebih lama):

1. **`datasets/audit/gold_audit.sql`** — 5 semantic view dasar plus view
   pembangun (`corr_*`) di baliknya. File ini isinya campuran — ada blok
   `CREATE VIEW` (DDL sungguhan) dan ada blok `SELECT` (cuma audit/investigasi).
   Baca dulu isi filenya sebelum jalankan, jangan asumsikan semua barisnya DDL.
2. **9 view journey (lintas-domain)** — DDL-nya ada di
   `datasets/audit/20_gold_journey_fase_a_draft.sql` (3 view) dan
   `datasets/audit/21_gold_journey_fase_b_draft.sql` (4 view) — meski nama
   filenya ada kata "draft", isinya `CREATE VIEW` sungguhan, sudah dikonfirmasi.
3. **`datasets/gold/23_rpt_sat_promo_material_december_semantic.sql`** — SAT
   Promo.
4. **`datasets/gold/24_rpt_sap_customer_office_material_month_semantic.sql`**
   — breakdown customer + sales_office untuk Sales/Sell-In. File ini punya
   **2 statement `CREATE VIEW`**. Jalankan **masing-masing statement secara
   terpisah** (highlight 1 `CREATE VIEW` penuh, run, baru lanjut yang
   kedua) — jangan select-all-run seluruh file sekaligus, karena pola serupa
   di file B2B (poin 5) pernah menyebabkan `ParseException` di Workbench,
   dan kombinasi ini di file 24 belum pernah benar-benar dites aman sebagai
   satu blok.
5. **`datasets/gold/25a_rpt_b2b_customer_branch_estore_semantic.sql`** dan
   **`datasets/gold/25b_rpt_b2b_customer_material_plu_semantic.sql`** —
   breakdown customer B2B. Sudah sengaja dipisah jadi 2 file karena
   menjalankan gabungannya sebagai 1 blok pernah gagal dengan
   `ParseException` di Workbench sebelumnya. Jalankan masing-masing file
   apa adanya, satu per satu.
6. **`datasets/gold/26_rpt_service_level_sales_office_semantic.sql`** —
   breakdown sales_office untuk Service Level. Cuma 1 statement, aman
   dijalankan langsung tanpa perlu dipecah.

### Setelah tiap `CREATE VIEW` — jalankan verifikasi berpasangannya

Tiap file gold view di atas punya file pasangan di `datasets/audit/` berisi
query verifikasi (duplicate-grain check, reconciliation ke total yang sudah
governed). Jalankan itu **segera setelah** `CREATE VIEW`-nya berhasil, jangan
tunda sampai semua view selesai dibuat — supaya kalau ada yang salah,
ketahuan lebih awal sebelum menumpuk masalah:

- Duplicate-grain check harus hasilnya **`0`** baris.
- Reconciliation (`SUM(...)` dari view baru vs total yang sudah governed
  untuk periode yang sama) harus **cocok** — selisih kecil karena pembulatan
  desimal (misal `.9124` vs `.00`) itu wajar, tapi selisih besar berarti ada
  yang salah (data belum ter-copy penuh di Langkah 1, atau `GROUP BY` di
  view-nya kurang lengkap).

---

## Langkah 3 — Ubah konfigurasi koneksi, BUKAN kode

Tidak ada satu pun baris di `tempo_core.ossie.yaml` atau
`backend/app/ossie/*.py` yang perlu diubah — semuanya merujuk ke nama
`gold.<nama_view>`, bukan ke host fisik. Yang perlu diubah cuma pengaturan
koneksi, semuanya sudah didaftar (dengan placeholder) di
`docs/cai-application-deployment-config.md`:

- **`IMPALA_HOST`** — ganti ke hostname coordinator Impala di cluster
  Private Cloud yang baru. **Ini satu-satunya nilai yang wajib diganti, tidak
  boleh disalin dari environment lama** — karena memang berbeda cluster.
- Cek ulang (jangan asumsikan sama): `IMPALA_PORT`, `IMPALA_AUTH_MECHANISM`,
  `IMPALA_USE_SSL`, `IMPALA_USE_HTTP_TRANSPORT`, `IMPALA_HTTP_PATH` — Private
  Cloud on-prem kadang punya konfigurasi otentikasi berbeda dari Cloudera di
  AWS (misal Kerberos alih-alih LDAP, atau port default beda).
- Setiap tool custom Agent Studio di
  `projects/tempo_scan_impala/agent_studio_tools/*/` juga menyimpan
  kredensial Impala-nya sendiri sebagai User Parameters (bukan environment
  variable — Configure UI Agent Studio memang tidak punya kolom env var
  terpisah) — perlu diupdate satu per satu, tool demi tool, saat workflow
  Agent Studio dibangun ulang di environment baru.

---

## Langkah 4 — Validasi kontrak semantic layer di cluster baru

```bash
PYTHONPATH=backend python3 scripts/validate_tempo_impala_contract.py --json
```

Harapannya: `valid: true`, `datasets: 20`, `metrics: 61`,
`golden_questions: 81`. Perlu diketahui: validator ini cuma mengecek bentuk
kontrak YAML/Python, **bukan** koneksi Impala yang sesungguhnya — jadi dia
akan tetap lolos meski `IMPALA_HOST` belum diset ke cluster baru.

Untuk verifikasi yang benar-benar menyentuh data di cluster baru:
1. Ulangi semua query reconciliation dari Langkah 2 sekali lagi secara
   end-to-end.
2. Jalankan beberapa golden question lewat CLI tool `resolve_semantic_object`
   dan `execute_governed_metric_query`, arahkan ke `IMPALA_HOST` cluster
   baru, pastikan hasil query benar-benar keluar (bukan cuma resolve metric
   berhasil tanpa eksekusi).

---

## Yang TIDAK perlu dipindah/diubah

- `tempo_core.ossie.yaml`, `tempo_governance.yaml`, `golden_questions.yaml`
  — murni konfigurasi, isinya cuma nama schema/view, tidak ada info koneksi
  fisik apa pun.
- `backend/app/ossie/*.py` — kode resolver/registry, tidak menyentuh host
  secara langsung (baca dari environment variable/Settings).
- Kode Python tool Agent Studio
  (`projects/tempo_scan_impala/agent_studio_tools/*/tool.py`) — cuma nilai
  `UserParameters`-nya (kredensial Impala) yang perlu diupdate, bukan
  kodenya.

---

## Migrasi Agent Studio artifact (tugas kedua, ditunda dulu)

Ditunda secara sengaja — sedang dicoba lewat menu export/import bawaan UI
Agent Studio secara langsung, bukan lewat script. Akan didokumentasikan
terpisah setelah hasil percobaan UI itu diketahui.
