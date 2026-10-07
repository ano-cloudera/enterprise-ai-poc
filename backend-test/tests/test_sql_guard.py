from app.sql.guard import validate_readonly_sql


def test_allows_silver_select_with_limit_cap() -> None:
    result = validate_readonly_sql(
        "SELECT material, SUM(sell_in_bill_val) AS v FROM silver.sales_oct_dec_2024 GROUP BY material",
        max_rows=50,
    )
    assert result.ok
    assert "LIMIT 50" in (result.sql or "").upper()


def test_rejects_ddl() -> None:
    result = validate_readonly_sql("DROP TABLE silver.sales_oct_dec_2024", max_rows=10)
    assert not result.ok
