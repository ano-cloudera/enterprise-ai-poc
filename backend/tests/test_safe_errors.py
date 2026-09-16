import pytest

from app.core.schemas import ChatRequest
from app.services import chat


@pytest.mark.asyncio
async def test_safe_error_response_does_not_expose_exception(monkeypatch):
    async def fail(_):
        raise RuntimeError("database-password-secret")

    monkeypatch.setattr(chat.workflow, "ainvoke", fail)
    response = await chat.run_chat(ChatRequest(question="sales by region"))
    assert response.status == "error"
    assert "database-password-secret" not in response.model_dump_json()
    assert response.metadata.trace_id
