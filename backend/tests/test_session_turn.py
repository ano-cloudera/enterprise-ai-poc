from app.services.conversational import TurnUnderstanding
from app.services.session_turn import infer_turn_kind, should_apply_session_follow_up


def test_llm_new_topic_overrides_session() -> None:
    ctx = {"last_metric": "material_sell_in_value", "last_dimensions": ["material"]}
    q = "Tampilkan 10 material dengan rasio bill-to-PO terendah di Desember 2024"
    u = TurnUnderstanding(
        is_conversational=False,
        attach_domain_catalog=False,
        pipeline_question=q,
        turn_kind="new_topic",
        referential_follow_up=False,
        rationale="mode_follow_up",
    )
    assert infer_turn_kind(q, understanding=u, analysis_context=ctx) == "new_topic"
    assert not should_apply_session_follow_up(q, understanding=u, analysis_context=ctx)


def test_llm_explain_prior_for_november() -> None:
    ctx = {"last_metric": "material_sell_in_value", "last_dimensions": ["calmonth"]}
    q = "kenapa bulan nov itu terlihat paling rendah ya, bisa bantu analisa gak?"
    u = TurnUnderstanding(
        is_conversational=False,
        attach_domain_catalog=False,
        pipeline_question=q,
        turn_kind="explain_prior",
        referential_follow_up=True,
        rationale="mode_follow_up",
    )
    assert infer_turn_kind(q, understanding=u, analysis_context=ctx) == "explain_prior"
    assert should_apply_session_follow_up(q, understanding=u, analysis_context=ctx)


def test_heuristic_fallback_when_llm_skipped() -> None:
    ctx = {"last_metric": "material_sell_in_value", "last_dimensions": ["calmonth"]}
    q = "kenapa bulan nov itu terlihat paling rendah ya, bisa bantu analisa gak?"
    u = TurnUnderstanding(
        is_conversational=False,
        attach_domain_catalog=False,
        pipeline_question=q,
        rationale="skip_session_has_no_catalog_or_clarify",
    )
    assert infer_turn_kind(q, understanding=u, analysis_context=ctx) == "explain_prior"
