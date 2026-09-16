import pytest
from pydantic import ValidationError

from app.core.schemas import ChatResponse, ui_action_adapter
from app.semantic.loader import load_semantic_project
from app.tools.ui_actions import validate_action_targets


@pytest.mark.parametrize("action", [
    {"type": "SET_FILTER", "target": "region", "value": ["Jawa Barat"]},
    {"type": "SET_DATE_RANGE", "value": "current_month"},
    {"type": "CHANGE_METRIC", "value": "net_sales"},
    {"type": "CHANGE_DIMENSION", "value": "product"},
    {"type": "RENDER_CHART", "target": "chat", "value": {"chart_type": "bar", "dimension": "product", "metric": "net_sales"}},
    {"type": "SHOW_TABLE", "target": "chat", "value": {"columns": ["product", "value"]}},
    {"type": "HIGHLIGHT_CARD", "target": "region", "value": ["Jawa Barat"]},
    {"type": "RESET_FILTER"},
])
def test_every_ui_action_schema(action):
    assert ui_action_adapter.validate_python(action)


def test_unknown_ui_action_rejected():
    with pytest.raises(ValidationError):
        ui_action_adapter.validate_python({"type": "RUN_JAVASCRIPT", "value": "alert(1)"})


def test_malformed_ui_action_rejected():
    with pytest.raises(ValidationError):
        ui_action_adapter.validate_python({"type": "SET_FILTER", "target": "region", "value": "Jawa Barat"})


def test_unknown_semantic_ui_target_rejected():
    action = ui_action_adapter.validate_python({"type": "SET_FILTER", "target": "secret_field", "value": ["x"]})
    with pytest.raises(ValueError):
        validate_action_targets([action], load_semantic_project("tempo_scan"))


def test_canonical_response_contract():
    response = ChatResponse.model_validate({
        "status": "ok", "question": "Question",
        "answer": {"summary": "Answer", "drivers": [], "recommended_actions": [], "caveats": []},
        "data": {"columns": [], "rows": []}, "chart_spec": None, "ui_actions": [],
        "metadata": {"trace_id": "trace", "session_id": "session", "intent": "analytical", "resolved_context": {}, "execution_time_ms": 1},
    })
    assert set(response.model_dump()) == {"status", "question", "answer", "data", "chart_spec", "ui_actions", "metadata"}
    assert set(response.metadata.model_dump()) == {"trace_id", "session_id", "intent", "resolved_context", "execution_time_ms"}
