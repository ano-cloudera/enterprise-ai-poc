--CREATE TABLE FOR GOLD


CREATE VIEW gold.rpt_sap_monthly_executive AS SELECT m.calmonth, s.sales_bill_val, s.sales_bill_qty, s.sales_do_qty, s.sales_do_amt, s.sales_materials, sc.sales_customers, st.stock_qty, st.stock_val, st.stock_materials, sv.svc_do_qty, sv.svc_po_qty, sv.svc_fill_rate, sv.svc_materials, b.b2b_bill_val, b.b2b_bill_qty, b.b2b_materials, bc.b2b_customers, CASE WHEN s.sales_bill_val > 0 THEN s.sales_do_amt / s.sales_bill_val END do_amt_to_bill_val_ratio, CASE WHEN s.sales_bill_qty > 0 THEN st.stock_qty / s.sales_bill_qty END stock_to_sales_bill_qty_ratio FROM (SELECT calmonth FROM gold.corr_sales_material_month UNION SELECT calmonth FROM gold.corr_stock_material_month UNION SELECT calmonth FROM gold.corr_b2b_material_month) m LEFT OUTER JOIN (SELECT calmonth, sum(bill_val) sales_bill_val, sum(bill_qty) sales_bill_qty, sum(do_qty) sales_do_qty, sum(do_amt) sales_do_amt, count(DISTINCT material) sales_materials FROM gold.corr_sales_material_month GROUP BY calmonth) s ON m.calmonth = s.calmonth LEFT OUTER JOIN (SELECT calmonth, count(DISTINCT customer) sales_customers FROM gold.corr_sales_customer_month GROUP BY calmonth) sc ON m.calmonth = sc.calmonth LEFT OUTER JOIN (SELECT calmonth, sum(tot_stck) stock_qty, sum(val_stck) stock_val, count(DISTINCT material) stock_materials FROM gold.corr_stock_material_month GROUP BY calmonth) st ON m.calmonth = st.calmonth LEFT OUTER JOIN (SELECT calmonth, sum(do_qty) svc_do_qty, sum(po_qty) svc_po_qty, sum(do_qty) / if(sum(po_qty) IS DISTINCT FROM 0, sum(po_qty), NULL) svc_fill_rate, count(DISTINCT material) svc_materials FROM gold.corr_service_material_month GROUP BY calmonth) sv ON m.calmonth = sv.calmonth LEFT OUTER JOIN (SELECT calmonth, sum(bill_val) b2b_bill_val, sum(bill_qty) b2b_bill_qty, count(DISTINCT material) b2b_materials FROM gold.corr_b2b_material_month GROUP BY calmonth) b ON m.calmonth = b.calmonth LEFT OUTER JOIN (SELECT calmonth, count(DISTINCT customer) b2b_customers FROM gold.corr_b2b_customer_month GROUP BY calmonth) bc ON m.calmonth = bc.calmonth



CREATE VIEW gold.rpt_service_level_material_month AS SELECT v.calmonth, v.material, v.do_qty, v.po_qty, v.fill_rate, s.bill_qty sales_bill_qty, s.bill_val sales_bill_val, t.tot_stck, CASE WHEN v.fill_rate < 0.5 THEN 'low_fill' WHEN v.fill_rate < 0.8 THEN 'medium_fill' ELSE 'high_fill' END fill_rate_band FROM gold.corr_service_material_month v LEFT OUTER JOIN gold.corr_sales_material_month s ON v.calmonth = s.calmonth AND v.material = s.material LEFT OUTER JOIN gold.corr_stock_material_month t ON v.calmonth = t.calmonth AND v.material = t.material


CREATE VIEW gold.rpt_sales_office_performance AS WITH `keys` AS (SELECT sales_off FROM gold.corr_sales_sales_office UNION SELECT sales_off FROM gold.corr_picking_sales_office UNION SELECT sales_off FROM gold.corr_unloading_sales_office) SELECT k.sales_off, s.bill_val sales_bill_val, s.sales_lines, p.delay_rate picking_delay_rate, p.avg_pick_min, p.pick_rows, u.avg_unload_min, u.unload_rows, s.sales_off IS NOT NULL has_sales, p.sales_off IS NOT NULL has_picking, u.sales_off IS NOT NULL has_unloading, CASE WHEN s.sales_lines > 0 THEN CAST(p.pick_rows AS DOUBLE) / s.sales_lines END pick_rows_per_sales_line FROM `keys` k LEFT OUTER JOIN gold.corr_sales_sales_office s ON k.sales_off = s.sales_off LEFT OUTER JOIN gold.corr_picking_sales_office p ON k.sales_off = p.sales_off LEFT OUTER JOIN gold.corr_unloading_sales_office u ON k.sales_off = u.sales_off

CREATE VIEW gold.rpt_sap_customer_reconciliation AS SELECT s.calmonth, s.customer, s.bill_val sales_bill_val, b.bill_val b2b_bill_val, s.bill_val - b.bill_val bill_val_variance, CASE WHEN b.bill_val > 0 THEN s.bill_val / b.bill_val END sales_to_b2b_ratio, CASE WHEN b.bill_val > 0 THEN abs(s.bill_val - b.bill_val) / b.bill_val END bill_val_pct_variance FROM gold.corr_sales_customer_month s INNER JOIN gold.corr_b2b_customer_month b ON s.customer = b.customer AND s.calmonth = b.calmonth


CREATE VIEW gold.corr_sales_material_month AS SELECT c_0calmonth calmonth, material, sum(bill_val) * 100 bill_val, sum(c_0bill_qty) bill_qty, sum(do_qty) do_qty, sum(coalesce(do_amt, do_amount)) * 100 do_amt FROM silver.sales_oct_dec_2024 WHERE c_0calmonth IS NOT NULL AND material IS NOT NULL GROUP BY c_0calmonth, material


CREATE VIEW gold.corr_sales_customer_month AS SELECT c_0calmonth calmonth, c_0customer customer, sum(bill_val) * 100 bill_val FROM silver.sales_oct_dec_2024 WHERE c_0calmonth IS NOT NULL AND c_0customer IS NOT NULL GROUP BY c_0calmonth, c_0customer

CREATE VIEW gold.corr_sales_sales_office AS SELECT lpad(trim(CAST(c_0sales_off AS STRING)), 4, '0') sales_off, sum(bill_val) * 100 bill_val, count(*) sales_lines FROM silver.sales_oct_dec_2024 WHERE c_0sales_off IS NOT NULL AND trim(CAST(c_0sales_off AS STRING)) != '' GROUP BY lpad(trim(CAST(c_0sales_off AS STRING)), 4, '0')


CREATE VIEW gold.corr_stock_material_month AS SELECT c_0calmonth calmonth, c_0material material, sum(totstck) tot_stck, sum(valstck) val_stck FROM silver.stock_tempo_oct_dec_2024 WHERE c_0calmonth IS NOT NULL AND c_0material IS NOT NULL GROUP BY c_0calmonth, c_0material


CREATE VIEW gold.corr_service_material_month AS SELECT c_0calmonth calmonth, c_0material material, sum(do_qty) do_qty, sum(po_qty) po_qty, CASE WHEN sum(po_qty) > 0 THEN sum(do_qty) / sum(po_qty) END fill_rate FROM silver.service_level_oct_dec_2024 WHERE c_0calmonth IS NOT NULL AND c_0material IS NOT NULL GROUP BY c_0calmonth, c_0material


CREATE VIEW gold.corr_b2b_material_month AS SELECT c_0calmonth calmonth, c_0material material, max(regexp_replace(trim(CAST(kode_plu AS STRING)), '\\.0$', '')) kode_plu, sum(bill_val) bill_val, sum(c_0bill_qty) bill_qty FROM silver.b2b_oct_dec_2024 WHERE c_0calmonth IS NOT NULL AND c_0material IS NOT NULL GROUP BY c_0calmonth, c_0material


CREATE VIEW gold.corr_b2b_customer_month AS SELECT c_0calmonth calmonth, c_0customer customer, sum(bill_val) bill_val FROM silver.b2b_oct_dec_2024 WHERE c_0calmonth IS NOT NULL AND c_0customer IS NOT NULL GROUP BY c_0calmonth, c_0customer


CREATE VIEW gold.corr_picking_sales_office AS SELECT lpad(trim(CAST(sales_office AS STRING)), 4, '0') sales_off, avg(CASE WHEN sstatus = 'Delayed' THEN 1.0 ELSE 0 END) delay_rate, avg(imenitpick) avg_pick_min, count(*) pick_rows FROM silver.picking_okt_des_24 WHERE sales_office IS NOT NULL AND trim(CAST(sales_office AS STRING)) != '' GROUP BY lpad(trim(CAST(sales_office AS STRING)), 4, '0')


CREATE VIEW gold.corr_unloading_sales_office AS SELECT lpad(trim(CAST(sales_office AS STRING)), 4, '0') sales_off, avg(imenit) avg_unload_min, count(*) unload_rows FROM silver.unloading_okt_des_24 WHERE sales_office IS NOT NULL AND trim(CAST(sales_office AS STRING)) != '' GROUP BY lpad(trim(CAST(sales_office AS STRING)), 4, '0')
