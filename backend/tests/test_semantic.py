from app.semantic.loader import allowed_columns, allowed_tables, load_semantic_project


def test_tempo_semantic_model_loads():
    project = load_semantic_project("tempo_scan")
    assert "commercial_sales" in project.datasets
    assert "commercial_inventory" in project.datasets
    assert "commercial_sales_daily" in allowed_tables(project)
    assert "sales_amount" in allowed_columns(project)
    assert project.datasets["commercial_sales"].metrics["net_sales"].aggregation == "sum"
