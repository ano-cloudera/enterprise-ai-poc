# Legacy Impala / CDW Mapping Checklist

This scaffold is retained for compatibility. Trino is the current Milestone 5 production CDW target; do not treat this checklist as the active implementation plan.

The local app uses business-ready tables named:
- `commercial_sales_daily`
- `commercial_inventory_daily`

For Tempo real data, either create views with these contracts or update the project semantic YAML and any dashboard SQL together.

## Sales view expected columns

`sales_date, region_name, province, city, product_id, product_name, product_category, brand, outlet_id, outlet_name, outlet_type, channel_id, channel_name, customer_segment, sales_amount, sales_qty, transaction_count, avg_selling_price`

## Inventory view expected columns

`inventory_date, product_id, product_name, product_category, outlet_id, outlet_name, region_name, city, opening_stock, closing_stock, available_stock, stockout_flag, days_of_supply`

## Connection rules

- Use a read-only user.
- Prefer TLS/enterprise auth in customer environment.
- Never expose username/password to the browser.
- Set a query timeout at the driver or proxy level for the final CAI deployment.
- Keep AI access limited to curated/governed views.
