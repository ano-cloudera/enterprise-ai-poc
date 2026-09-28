-- TEMPO semantic metric catalog (documentation view)
-- Source-controlled definition:
-- datasets/audit/TEMPO_SEMANTIC_FIELD_CATALOG.md
--
-- This view contains metadata only. It does not calculate business KPIs.
-- DEPLOY LAST: run only after all semantic source views are finalized.
-- During development, update this file without repeatedly deploying it.

DROP VIEW IF EXISTS gold.rpt_semantic_metric_catalog;

CREATE VIEW gold.rpt_semantic_metric_catalog AS
WITH metric_catalog AS (

SELECT
  'FL-01' AS metric_id,
  'gold.rpt_service_level_material_month_semantic' AS source_view,
  'service_fill_rate' AS physical_field,
  'Fill Rate' AS business_name,
  'SUM(service_do_qty) / NULLIF(SUM(service_po_qty), 0)' AS formula,
  'ratio_percent' AS unit,
  'calmonth + material' AS grain,
  'Persentase jumlah pesanan yang berhasil dipenuhi.' AS business_description,
  'Pada level aggregate wajib dihitung ulang dari total DO dan PO.' AS caveat,
  'approved_candidate' AS governance_status,
  '2026-09-24' AS effective_date

UNION ALL

SELECT
  'FL-06',
  'gold.rpt_service_level_material_month_semantic',
  'fill_rate_band',
  'Fill Rate Band',
  'unknown if NULL; low_fill if <0.5; medium_fill if 0.5 to <0.8; high_fill if >=0.8',
  'category',
  'calmonth + material',
  'Klasifikasi tingkat pemenuhan order untuk prioritas investigasi material.',
  'Threshold masih memerlukan persetujuan bisnis.',
  'fixed_pending_business_approval',
  '2026-09-24'

UNION ALL

SELECT
  'FL-04',
  'gold.rpt_service_level_material_month_semantic',
  'service_po_qty',
  'Purchase Order Quantity',
  'SUM(service_po_qty)',
  'quantity',
  'calmonth + material',
  'Jumlah unit yang dipesan customer.',
  'Gunakan sebagai denominator Fill Rate.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'FL-05',
  'gold.rpt_service_level_material_month_semantic',
  'service_do_qty',
  'Fulfilled Delivery Quantity',
  'SUM(service_do_qty)',
  'quantity',
  'calmonth + material',
  'Jumlah unit yang berhasil dikirim atau dipenuhi.',
  'Gunakan sebagai numerator Fill Rate.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'SO-06',
  'gold.rpt_sap_customer_reconciliation_semantic',
  'sell_in_minus_sell_out_val',
  'Sell-In Minus Sell-Out Value',
  'SUM(sell_in_bill_val) - SUM(sell_out_bill_val)',
  'IDR',
  'calmonth + customer',
  'Selisih nilai Sell-In dan Sell-Out. Positif berarti Sell-In lebih besar.',
  'Hanya customer yang tersedia pada Sales dan B2B.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'SO-07',
  'gold.rpt_sap_customer_reconciliation_semantic',
  'sell_out_to_sell_in_value_ratio',
  'Sell-Out to Sell-In Value Ratio',
  'SUM(sell_out_bill_val) / NULLIF(SUM(sell_in_bill_val), 0)',
  'ratio_percent',
  'calmonth + customer',
  'Mengukur keseimbangan nilai Sell-Out terhadap Sell-In.',
  'Bukan official sell-through karena opening stock dan perbedaan price basis belum diperhitungkan.',
  'approved_candidate_with_caveat',
  '2026-09-24'

UNION ALL

SELECT
  'SO-07-INVERSE',
  'gold.rpt_sap_customer_reconciliation_semantic',
  'sell_in_to_sell_out_value_ratio',
  'Sell-In to Sell-Out Value Ratio',
  'SUM(sell_in_bill_val) / NULLIF(SUM(sell_out_bill_val), 0)',
  'ratio',
  'calmonth + customer',
  'Perspektif kebalikan untuk melihat berapa kali Sell-In dibanding Sell-Out.',
  'Gunakan sebagai metric pendukung, bukan KPI utama.',
  'supporting',
  '2026-09-24'

UNION ALL

SELECT
  'SO-06-PCT',
  'gold.rpt_sap_customer_reconciliation_semantic',
  'absolute_variance_rate_vs_sell_out',
  'Sell-In vs Sell-Out Absolute Variance Rate',
  'ABS(SUM(sell_in_bill_val) - SUM(sell_out_bill_val)) / NULLIF(SUM(sell_out_bill_val), 0)',
  'ratio_percent',
  'calmonth + customer',
  'Besarnya gap absolut relatif terhadap nilai Sell-Out.',
  'Tidak menunjukkan arah. Gunakan bill_val_variance untuk arah.',
  'supporting',
  '2026-09-24'

UNION ALL

SELECT
  'SI-01-SHARED',
  'gold.rpt_sap_customer_reconciliation_semantic',
  'sell_in_bill_val',
  'Shared-Customer Sell-In Value',
  'SUM(sell_in_bill_val)',
  'IDR',
  'calmonth + customer',
  'Nilai Sell-In untuk customer yang juga ditemukan pada B2B.',
  'Bukan total seluruh customer Sales.',
  'scoped_metric',
  '2026-09-24'

UNION ALL

SELECT
  'SO-01-SHARED',
  'gold.rpt_sap_customer_reconciliation_semantic',
  'sell_out_bill_val',
  'Shared-Customer Sell-Out Value',
  'SUM(sell_out_bill_val)',
  'IDR',
  'calmonth + customer',
  'Nilai Sell-Out untuk shared-customer scope.',
  'Hanya customer yang tersedia pada Sales dan B2B.',
  'scoped_metric',
  '2026-09-24'

UNION ALL

SELECT
  'SI-13-Q4',
  'gold.rpt_sales_office_performance_semantic',
  'sell_in_bill_val',
  'Sales Office Sell-In Value (Q4)',
  'SUM(sell_in_bill_val)',
  'IDR',
  'reporting_period + sales_office',
  'Total nilai Sell-In per sales office untuk seluruh Q4 2024.',
  'View tidak mendukung tren bulanan.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'PK-01-Q4',
  'gold.rpt_sales_office_performance_semantic',
  'picking_delay_rate',
  'Picking Delay Rate (Q4)',
  'delayed pick rows / total pick rows',
  'ratio_percent',
  'reporting_period + sales_office',
  'Proporsi baris picking berstatus Delayed per sales office selama Q4.',
  'Hanya 23 dari 52 offices memiliki data Picking.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'PK-03-Q4',
  'gold.rpt_sales_office_performance_semantic',
  'average_picking_minutes',
  'Average Picking Time (Q4)',
  'AVG(imenitpick)',
  'minutes',
  'reporting_period + sales_office',
  'Rata-rata durasi picking per sales office selama Q4.',
  'Tidak tersedia untuk office tanpa data Picking.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'UL-01-Q4',
  'gold.rpt_sales_office_performance_semantic',
  'average_unloading_minutes',
  'Average Unloading Time (Q4)',
  'AVG(imenit)',
  'minutes',
  'reporting_period + sales_office',
  'Rata-rata durasi unloading per sales office selama Q4.',
  'Hanya 14 dari 52 offices memiliki data Unloading.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'XD-03-Q4',
  'gold.rpt_sales_office_performance_semantic',
  'picking_rows_per_sales_line',
  'Picking Rows per Sales Line (Q4)',
  'picking_rows / NULLIF(sales_billing_lines, 0)',
  'ratio',
  'reporting_period + sales_office',
  'Proxy intensitas workload picking dibanding jumlah billing line.',
  'Bukan productivity rate dan tidak mendukung tren bulanan.',
  'supporting',
  '2026-09-24'

UNION ALL

SELECT
  'SI-01',
  'gold.rpt_sap_monthly_executive_semantic',
  'sales_bill_val',
  'Monthly Sell-In Billing Value',
  'SUM(sales_bill_val)',
  'IDR',
  'calmonth',
  'Total nilai Sell-In bulanan yang sudah dinormalisasi ke IDR pada Gold.',
  'Jangan menerapkan scaling 100 lagi.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'SI-02',
  'gold.rpt_sap_monthly_executive_semantic',
  'sales_bill_qty',
  'Monthly Sell-In Billing Quantity',
  'SUM(sales_bill_qty)',
  'quantity',
  'calmonth',
  'Total unit yang ditagihkan pada bulan berjalan.',
  'Gunakan sebagai volume billing, bukan jumlah dokumen.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'FL-01-EXEC',
  'gold.rpt_sap_monthly_executive_semantic',
  'svc_fill_rate',
  'Company Monthly Fill Rate',
  'SUM(svc_do_qty) / NULLIF(SUM(svc_po_qty), 0)',
  'ratio_percent',
  'calmonth',
  'Persentase pemenuhan order perusahaan per bulan.',
  'Pada rollup lintas bulan hitung ulang dari DO dan PO; jangan AVG monthly ratio.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'SI-DQ-01',
  'gold.rpt_sap_monthly_executive_semantic',
  'do_amt_to_bill_val_ratio',
  'DO Amount to Billing Value Ratio',
  'sales_do_amt / NULLIF(sales_bill_val, 0)',
  'ratio',
  'calmonth',
  'Indikator alignment nilai DO terhadap billing.',
  'Gunakan sebagai data-quality signal; December memiliki anomali yang perlu dijelaskan.',
  'data_quality_metric',
  '2026-09-24'

UNION ALL

SELECT
  'ST-SI-01',
  'gold.rpt_sap_monthly_executive_semantic',
  'stock_to_sales_bill_qty_ratio',
  'Stock to Sell-In Quantity Ratio',
  'stock_qty / NULLIF(sales_bill_qty, 0)',
  'ratio',
  'calmonth',
  'Proxy coverage stok gudang terhadap volume billing bulanan.',
  'Stock adalah snapshot; ratio tidak memperhitungkan inventory flow.',
  'supporting',
  '2026-09-24'

UNION ALL

SELECT
  'SI-01-MAT',
  'gold.rpt_sap_material_month_semantic',
  'sell_in_bill_val',
  'Material Sell-In Billing Value',
  'SUM(sell_in_bill_val)',
  'IDR',
  'calmonth + material',
  'Nilai Sell-In per material dan bulan.',
  'Wajib filter has_sell_in untuk scope Sales.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'SI-02-MAT',
  'gold.rpt_sap_material_month_semantic',
  'sell_in_bill_qty',
  'Material Sell-In Billing Quantity',
  'SUM(sell_in_bill_qty)',
  'quantity',
  'calmonth + material',
  'Volume billing Sell-In per material dan bulan.',
  'Wajib filter has_sell_in untuk scope Sales.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'ST-01-MAT',
  'gold.rpt_sap_material_month_semantic',
  'warehouse_stock_qty',
  'Material Warehouse Stock Quantity',
  'SUM(warehouse_stock_qty)',
  'quantity',
  'calmonth + material',
  'Snapshot total stok gudang Tempo per material dan bulan.',
  'Stock adalah snapshot; jangan menjumlahkan antarbulan sebagai inventory flow.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'FL-01-MAT',
  'gold.rpt_sap_material_month_semantic',
  'service_fill_rate',
  'Material Fill Rate',
  'SUM(service_do_qty) / NULLIF(SUM(service_po_qty), 0)',
  'ratio_percent',
  'calmonth + material',
  'Tingkat pemenuhan order per material dan bulan.',
  'Wajib filter has_service_level; rollup dihitung ulang dari DO dan PO.',
  'approved_candidate',
  '2026-09-24'

UNION ALL

SELECT
  'SO-01-MAT',
  'gold.rpt_sap_material_month_semantic',
  'sell_out_bill_val',
  'Material Sell-Out Billing Value',
  'SUM(sell_out_bill_val)',
  'IDR',
  'calmonth + material',
  'Nilai Sell-Out B2B per material dan bulan.',
  'Hanya material B2B; wajib filter has_sell_out.',
  'scoped_metric',
  '2026-09-24'

UNION ALL

SELECT
  'SO-07-MAT',
  'gold.rpt_sap_material_month_semantic',
  'sell_out_to_sell_in_value_ratio',
  'Material Sell-Out to Sell-In Value Ratio',
  'SUM(sell_out_bill_val) / NULLIF(SUM(sell_in_bill_val), 0)',
  'ratio_percent',
  'calmonth + material',
  'Perbandingan nilai Sell-Out terhadap Sell-In per material dan bulan.',
  'Wajib filter has_sell_in dan has_sell_out; price basis dapat berbeda.',
  'approved_candidate_with_caveat',
  '2026-09-24'

UNION ALL

SELECT
  'SI-16-MAT',
  'gold.rpt_sap_material_month_semantic',
  'sell_in_qty_per_stock_unit',
  'Sell-In Quantity per Stock Unit',
  'SUM(sell_in_bill_qty) / NULLIF(SUM(warehouse_stock_qty), 0)',
  'ratio',
  'calmonth + material',
  'Proxy velocity Sell-In terhadap snapshot stok.',
  'Bukan inventory turnover resmi; wajib filter has_sell_in dan has_stock.',
  'supporting',
  '2026-09-24'

UNION ALL

SELECT
  'SI-DQ-02',
  'gold.rpt_sap_material_month_semantic',
  'sales_do_amt_to_bill_val_ratio',
  'Material DO Amount to Billing Value Ratio',
  'SUM(sales_do_amt) / NULLIF(SUM(sell_in_bill_val), 0)',
  'ratio',
  'calmonth + material',
  'Data-quality signal antara nilai delivery order dan billing.',
  'Gunakan sebagai alignment check, bukan revenue KPI.',
  'data_quality_metric',
  '2026-09-24'
)

SELECT
  c.*,

  CASE
    WHEN c.metric_id IN (
      'SO-07-INVERSE',
      'SO-06-PCT',
      'SI-01-SHARED',
      'SO-01-SHARED',
      'SI-DQ-01',
      'ST-SI-01',
      'SI-DQ-02'
    )
    THEN 'audit_derived_from_irvan'
    ELSE 'irvan_kpi_catalog_adapted'
  END AS definition_origin,

  CASE c.metric_id
    WHEN 'FL-01' THEN 'FL-01'
    WHEN 'FL-04' THEN 'FL-04'
    WHEN 'FL-05' THEN 'FL-05'
    WHEN 'FL-06' THEN 'FL-06'
    WHEN 'SO-06' THEN 'SO-06'
    WHEN 'SO-07' THEN 'SO-07'
    WHEN 'SO-07-INVERSE' THEN 'SO-07'
    WHEN 'SO-06-PCT' THEN 'SO-06'
    WHEN 'SI-01-SHARED' THEN 'SI-01'
    WHEN 'SO-01-SHARED' THEN 'SO-01'
    WHEN 'SI-13-Q4' THEN 'SI-13'
    WHEN 'PK-01-Q4' THEN 'PK-01'
    WHEN 'PK-03-Q4' THEN 'PK-03'
    WHEN 'UL-01-Q4' THEN 'UL-01'
    WHEN 'XD-03-Q4' THEN 'XD-03'
    WHEN 'SI-01' THEN 'SI-01'
    WHEN 'SI-02' THEN 'SI-02'
    WHEN 'FL-01-EXEC' THEN 'FL-01'
    WHEN 'SI-DQ-01' THEN 'SI-05'
    WHEN 'ST-SI-01' THEN 'ST-06'
    WHEN 'SI-01-MAT' THEN 'SI-01'
    WHEN 'SI-02-MAT' THEN 'SI-02'
    WHEN 'ST-01-MAT' THEN 'ST-01'
    WHEN 'FL-01-MAT' THEN 'FL-01'
    WHEN 'SO-01-MAT' THEN 'SO-01'
    WHEN 'SO-07-MAT' THEN 'SO-07'
    WHEN 'SI-16-MAT' THEN 'SI-16'
    WHEN 'SI-DQ-02' THEN 'SI-05'
  END AS original_kpi_id,

  CASE
    WHEN c.metric_id = 'SO-07-INVERSE'
      THEN 'derived_inverse'
    WHEN c.metric_id = 'SO-06-PCT'
      THEN 'derived_variance_rate'
    WHEN c.metric_id LIKE '%-SHARED'
      THEN 'scoped_shared_customer_variant'
    WHEN c.metric_id LIKE '%-Q4'
      THEN 'scoped_q4_variant'
    WHEN c.metric_id LIKE '%-MAT'
      THEN 'scoped_material_variant'
    WHEN c.metric_id LIKE '%-EXEC'
      THEN 'scoped_executive_variant'
    WHEN c.metric_id LIKE '%-DQ-%'
      THEN 'data_quality_variant'
    WHEN c.metric_id = 'ST-SI-01'
      THEN 'contextual_ratio'
    ELSE 'semantic_field_rename'
  END AS adaptation_type,

  CASE
    WHEN c.governance_status = 'data_quality_metric'
      THEN 'internal_technical_review'
    ELSE 'pending_business_confirmation'
  END AS business_approval_status

FROM metric_catalog c;

-- Validation
SELECT *
FROM gold.rpt_semantic_metric_catalog
ORDER BY source_view, metric_id;

SELECT
  definition_origin,
  adaptation_type,
  business_approval_status,
  COUNT(*) AS metric_count
FROM gold.rpt_semantic_metric_catalog
GROUP BY
  definition_origin,
  adaptation_type,
  business_approval_status
ORDER BY
  definition_origin,
  adaptation_type;

SELECT *
FROM gold.rpt_semantic_metric_catalog
WHERE original_kpi_id IS NULL;

-- Expected: 0 rows with NULL original_kpi_id.
