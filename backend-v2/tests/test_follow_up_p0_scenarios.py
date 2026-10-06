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
