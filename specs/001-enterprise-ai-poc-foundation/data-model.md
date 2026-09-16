# Logical Data Model

## Business-ready view: commercial_sales_daily

Grain: date + product + outlet + channel.

Key dimensions:
- sales_date
- region_name / province / city
- product_id / product_name / product_category / brand
- outlet_id / outlet_name / outlet_type
- channel_id / channel_name
- customer_segment

Measures:
- sales_amount (million IDR in synthetic data)
- sales_qty
- transaction_count
- avg_selling_price

## Business-ready view: commercial_inventory_daily

Grain: date + product + outlet.

Dimensions:
- inventory_date
- product
- outlet
- region / city

Measures:
- opening_stock
- closing_stock
- available_stock
- stockout_flag
- days_of_supply

## Future real model

The physical star schema may contain fact_sales, fact_inventory, dim_product, dim_outlet, dim_customer, dim_region, dim_channel and dim_date, but the AI should primarily query stable business-ready views rather than raw operational tables.
