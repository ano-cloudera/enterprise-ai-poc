"""Session turn classification: new topic vs continue vs explain prior (LLM + heuristic fallback)."""

from __future__ import annotations

from typing import Any, Literal

from app.services.session_context import (
    _continues_prior_ranking,
    _normalize_question_text,
    is_entity_time_series_follow_up,
    is_referential_follow_up,
    is_standalone_analytic_question,
)

TurnKind = Literal["new_topic", "continue_session", "explain_prior", "conversational"]

_LLM_SKIP_RATIONALES = frozenset(
    {
        "skip_session_has_no_catalog_or_clarify",
        "turn_understanding_failed_default_analytic",
    }
)


def infer_turn_kind(
    question: str,
    *,
    understanding: Any | None = None,
    analysis_context: dict[str, Any] | None = None,
) -> TurnKind:
    if understanding is not None and getattr(understanding, "is_conversational", False):
        return "conversational"

    rationale = str(getattr(understanding, "rationale", "") or "")
    llm_kind = getattr(understanding, "turn_kind", None)
    if (
        understanding is not None
        and llm_kind in ("new_topic", "continue_session", "explain_prior")
        and rationale not in _LLM_SKIP_RATIONALES
        and rationale.startswith("mode_")
    ):
        if llm_kind == "continue_session" and is_standalone_analytic_question(question):
            return "new_topic"
        if llm_kind == "new_topic":
            return "new_topic"
        return llm_kind

    if is_standalone_analytic_question(question):
        return "new_topic"

    from app.services.follow_up import _wants_history_only_explanation

    if _wants_history_only_explanation(question):
        return "explain_prior"

    if analysis_context and analysis_context.get("last_metric"):
        normalized = _normalize_question_text(question)
        if _continues_prior_ranking(normalized):
            return "continue_session"
        if (
            is_referential_follow_up(question)
            or is_entity_time_series_follow_up(question)
            or (understanding is not None and getattr(understanding, "referential_follow_up", False))
        ):
            return "continue_session"
        if not is_standalone_analytic_question(question):
            return "continue_session"

    return "new_topic"


def should_apply_session_follow_up(
    question: str,
    *,
    understanding: Any | None = None,
    analysis_context: dict[str, Any] | None = None,
) -> bool:
    kind = infer_turn_kind(question, understanding=understanding, analysis_context=analysis_context)
    return kind in ("continue_session", "explain_prior")
