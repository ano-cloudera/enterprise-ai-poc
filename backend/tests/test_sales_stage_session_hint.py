from app.services.follow_up import build_analysis_context, try_follow_up_governed_resolution
from app.semantic.context import SemanticContextService
from app.services.conversational import TurnUnderstanding


def test_sales_stage_skipped_when_prior_turn_was_sell_in_material() -> None:
    reg = SemanticContextService().registry
    q = "bisa tampilkan tren penjualan untuk produk 001-00-03 perbulan ya"
    hit = reg.resolve_ambiguity(q, session_last_metric="material_sell_in_value")
    assert hit is None


def test_material_trend_follow_up_resolves_despite_llm_non_referential() -> None:
    ctx = build_analysis_context(
        metric="material_sell_in_value",
        dimensions=["material"],
        entity_dimension="material",
        ranked_entities=[{"rank": 1, "id": "001-00-03", "dimension": "material"}],
        last_question="pareto penjualan Q4",
    )
    q = "bisa tampilkan tren penjualan untuk produk 001-00-03 perbulan ya"
    u = TurnUnderstanding(
        is_conversational=False,
        attach_domain_catalog=False,
        pipeline_question=q,
        referential_follow_up=False,
        rationale="explicit_material",
    )
    fu = try_follow_up_governed_resolution(q, ctx, u)
    assert fu is not None
    assert fu["metric"] == "material_sell_in_value"
    assert fu["dimensions"] == ["calmonth"]

    resolved = SemanticContextService().resolve(
        q,
        session_analysis_context=ctx,
        turn_understanding=u.model_dump(),
    )
    assert resolved.get("status") == "resolved"
    assert resolved.get("metric") == "material_sell_in_value"
    assert resolved.get("status") != "needs_clarification"
