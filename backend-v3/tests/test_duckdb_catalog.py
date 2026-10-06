from pathlib import Path

from app.db.duckdb_catalog import DuckDBCatalog


def test_list_and_query_seeded_tables(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    import duckdb

    con = duckdb.connect(str(db))
    con.execute("CREATE SCHEMA silver")
    con.execute("CREATE TABLE silver.demo AS SELECT 1 AS id, 'A' AS label")
    con.close()

    catalog = DuckDBCatalog(db, sql_max_rows=10)
    tables = catalog.list_tables()
    assert any(t["qualified"] == "silver.demo" for t in tables)
    result = catalog.run_sql("SELECT id, label FROM silver.demo")
    assert result["row_count"] == 1
