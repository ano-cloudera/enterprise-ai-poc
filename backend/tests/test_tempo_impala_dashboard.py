from __future__ import annotations

from app.services import dashboard


def test_impala_dashboard_maps_governed_metrics_without_changing_legacy_contract(
    monkeypatch,
) -> None:
    def fake_rows(metric: str, dimensions: list[str]):
        if metric == "gross_billing_value":
            return [
                {"calmonth": 202410, "metric_value": 100_000_000.0},
                {"calmonth": 202411, "metric_value": 110_000_000.0},
                {"calmonth": 202412, "metric_value": 121_000_000.0},
            ]
        if metric == "company_fill_rate":
            return [
                {"calmonth": 202410, "metric_value": 0.75},
                {"calmonth": 202411, "metric_value": 0.78},
                {"calmonth": 202412, "metric_value": 0.80},
            ]
        if metric == "sales_office_sell_in_value":
            return [{"sales_office": "0201", "metric_value": 80_000_000.0}]
        if metric == "material_sell_in_value":
            return [{"material": "035-28-07", "metric_value": 50_000_000.0}]
        if metric == "material_sell_out_value":
            return [{"metric_value": 90_000_000.0}]
        raise AssertionError((metric, dimensions))

    monkeypatch.setattr(dashboard, "_ossie_metric_rows", fake_rows)
    result = dashboard._get_ossie_dashboard_overview()

    assert result["profile"] == "impala_ossie"
    assert result["kpis"][0]["key"] == "gross_billing_value"
    assert result["kpis"][0]["value"] == 121_000_000.0
    assert result["kpis"][0]["format"] == "currency_idr"
    assert result["kpis"][2]["value"] == 80.0
    assert result["sales_trend"][-1] == {"month": "202412", "sales": 121.0}
    assert result["region_sales"][0]["region"] == "0201"
    assert result["top_products"][0]["product"] == "035-28-07"
    assert {row["channel"] for row in result["channel_share"]} == {
        "Sell-In",
        "Sell-Out",
    }
    assert "Q4 2024" in result["scope_badges"]

