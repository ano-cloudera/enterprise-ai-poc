from app.services.follow_up import build_analysis_context, plan_follow_up, try_follow_up_governed_resolution


def test_unloading_compare_follow_up_from_prior_office_codes() -> None:
    ctx = build_analysis_context(
        metric="average_unloading_minutes",
        dimensions=["sales_office"],
        entity_dimension="sales_office",
        ranked_entities=[],
        last_question="Bandingkan rata-rata unloading sales office 0201 vs 0202 Q4 2024",
    )
    q = "office mana yang lebih lambat dan selisihnya berapa menit?"
    plan = plan_follow_up(q, ctx)
    assert plan is not None
    assert plan.intent == "compare"
    assert plan.compare_entities is not None
    ids = {str(e["id"]) for e in plan.compare_entities}
    assert ids == {"0201", "0202"}


def test_service_level_worst_office_material_drill() -> None:
    ctx = build_analysis_context(
        metric="sales_office_service_fill_rate",
        dimensions=["sales_off"],
        entity_dimension="sales_off",
        ranked_entities=[{"rank": 1, "dimension": "sales_off", "id": "0245", "metric_value": 0.4}],
        last_question="Hitung service level cabang tempo urutkan SL terjelek Q4",
    )
    q = "cabang paling jelek tadi, top 5 material dengan fill rate terendah"
    res = try_follow_up_governed_resolution(q, ctx, understanding=None)
    assert res is not None
    assert res["metric"] == "sales_office_service_fill_rate"
    assert "material" in res["dimensions"]


def test_sales_office_compare_from_question_office_codes() -> None:
    ctx = build_analysis_context(
        metric="sales_office_material_sell_in_value",
        dimensions=["sales_office", "material"],
        entity_dimension="sales_office",
        ranked_entities=[{"rank": 1, "id": "0201", "dimension": "sales_office"}],
        last_question="Top 5 material sell-in office 0201 Q4 2024",
    )
    q = "bandingkan total sell-in office 0201 vs 0280 Q4 untuk konteks yang sama"
    res = try_follow_up_governed_resolution(q, ctx, understanding=None)
    assert res is not None
    assert res["metric"] == "sales_office_sell_in_value"
    assert "sales_office" in res["dimensions"]
    filters = " ".join(res.get("follow_up_entity_filters") or [])
    assert "0201" in filters and "0280" in filters


def test_pareto_top3_contribution_relimit() -> None:
    ctx = build_analysis_context(
        metric="material_sell_in_value",
        dimensions=["material"],
        entity_dimension="material",
        ranked_entities=[
            {"rank": 1, "id": "A", "dimension": "material"},
            {"rank": 2, "id": "B", "dimension": "material"},
            {"rank": 3, "id": "C", "dimension": "material"},
        ],
        last_question="pareto sell-in top produk",
    )
    plan = plan_follow_up("tiga produk teratas tadi, berapa persen kontribusi ke total sell-in?", ctx)
    assert plan is not None
    assert plan.intent == "relimit"
    assert plan.limit == 3


def test_stock_tempo_fe001_follow_up_metric() -> None:
    ctx = build_analysis_context(
        metric="material_warehouse_stock_quantity",
        dimensions=["calmonth"],
        entity_dimension=None,
        ranked_entities=[],
        last_question="total stok gudang Tempo company-wide Q4 2024",
    )
    q = "bagaimana stok material FE001 dibanding total tadi?"
    res = try_follow_up_governed_resolution(q, ctx, understanding=None)
    assert res is not None
    assert res["metric"] == "material_warehouse_stock_quantity"
    assert any("FE001" in p for p in res.get("follow_up_entity_filters") or [])
