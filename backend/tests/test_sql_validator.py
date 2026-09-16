import pytest

from app.semantic.loader import load_semantic_project
from app.tools.sql_validator import validate_readonly_sql


@pytest.fixture
def project():
    return load_semantic_project("tempo_scan")


def validate(sql: str, project):
    return validate_readonly_sql(sql, project)


def test_accepts_safe_select_and_adds_default_limit(project):
    result = validate("SELECT region_name, SUM(sales_amount) AS sales FROM commercial_sales_daily WHERE sales_date >= DATE '2024-03-01' GROUP BY region_name", project)
    assert result.valid
    assert "LIMIT 200" in result.sql.upper()


@pytest.mark.parametrize("verb", ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "MERGE"])
def test_rejects_prohibited_dml_and_ddl(project, verb):
    assert not validate(f"{verb} TABLE commercial_sales_daily", project).valid


def test_rejects_multiple_statements(project):
    assert not validate("SELECT 1; SELECT 2", project).valid


def test_rejects_select_star(project):
    assert not validate("SELECT * FROM commercial_sales_daily WHERE sales_date >= DATE '2024-03-01'", project).valid


def test_caps_oversized_limit(project):
    result = validate("SELECT region_name FROM commercial_sales_daily WHERE sales_date >= DATE '2024-03-01' LIMIT 99999", project)
    assert result.valid
    assert "LIMIT 500" in result.sql.upper()


def test_rejects_schema_qualified_table_not_in_semantic_source(project):
    assert not validate("SELECT region_name FROM secret.commercial_sales_daily WHERE sales_date >= DATE '2024-03-01'", project).valid


def test_validates_columns_per_table(project):
    assert not validate("SELECT stockout_flag FROM commercial_sales_daily WHERE sales_date >= DATE '2024-03-01'", project).valid


def test_enforces_date_filter(project):
    assert not validate("SELECT region_name, SUM(sales_amount) FROM commercial_sales_daily GROUP BY region_name", project).valid


def test_rejects_unknown_function(project):
    assert not validate("SELECT mystery_udf(sales_amount) FROM commercial_sales_daily WHERE sales_date >= DATE '2024-03-01'", project).valid
