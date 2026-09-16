import pytest

from app.core.schemas import ChatRequest
from app.services.chat import run_chat


@pytest.mark.asyncio
async def test_hero_question_returns_structured_answer(monkeypatch):
    # Default local config is mock LLM + DuckDB.
    response = await run_chat(ChatRequest(question="Kenapa sales Jawa Barat turun bulan ini?"))
    assert response.status in {"ok", "fallback"}
    assert response.answer.summary
    assert response.metadata.intent == "analytical"
    assert response.metadata.session_id == "demo-session"
    assert response.data.rows
    assert response.chart_spec is None or response.chart_spec.type in {"bar", "line", "table"}
    assert "stockout" not in response.answer.summary.lower()
    assert str(response.data.rows[0]["current_value"]) in response.answer.summary
    assert str(response.data.rows[0]["previous_value"]) in response.answer.summary
