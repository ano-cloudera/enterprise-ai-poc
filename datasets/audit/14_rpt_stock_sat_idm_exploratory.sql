-- Exploratory (non-governed v1): Stock SAT-IDM DC vs store by month.
-- Grain: year + month + dcname + plu

CREATE VIEW gold.rpt_stock_sat_idm_exploratory AS
SELECT
  thn,
  bln,
  dcname,
  plu,
  division,
  SUM(dcstock_qty) AS dcstock_qty,
  SUM(storestock_qty) AS storestock_qty,
  SUM(dcstock_val) AS dcstock_val,
  SUM(storestock_val) AS storestock_val
FROM gold.stg_stock_sat_idm
GROUP BY thn, bln, dcname, plu, division;

-- Catalog I03/I11: use this view only outside execute_governed_query until promoted to OSSIE v2.
