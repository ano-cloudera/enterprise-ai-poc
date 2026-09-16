from __future__ import annotations

import pytest

from app.core.schemas import DashboardState
from app.semantic.loader import load_semantic_project
from app.semantic.resolver import normalize_analytical_intent, resolve_analytical_intent
from app.tools.semantic_sql import generate_semantic_sql
from app.tools.sql_validator import validate_readonly_sql


PROJECT = load_semantic_project("tempo_scan")


@pytest.mark.parametrize("golden", PROJECT.golden_questions, ids=lambda item: item.id)
def test_project_golden_question_semantics_and_sql(golden):
    candidate = resolve_analytical_intent(golden.question, DashboardState.model_validate(golden.context).model_dump(), PROJECT)
    intent = normalize_analytical_intent(candidate, PROJECT)
    expected = golden.expected
    assert intent.metric == expected.metric
    assert intent.dimensions == expected.dimensions
    assert intent.pattern == expected.pattern
    assert intent.filters == expected.filters
    assert intent.time.period == expected.period
    assert intent.comparison.type == expected.comparison
    if golden.generates_sql:
        validation = validate_readonly_sql(generate_semantic_sql(intent, PROJECT), PROJECT)
        assert validation.valid, validation.error
