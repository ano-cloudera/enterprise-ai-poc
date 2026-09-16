from __future__ import annotations

import pytest

from app.api.routes import health as health_route
from app.core.config import Settings
from app.core.schemas import ChatRequest
from app.llm.models import ModelHealth
from app.llm.providers import LLMProviderError
from app.services import chat


@pytest.mark.asyncio
async def test_qwen_failure_uses_grounded_fallback_without_chat_error(monkeypatch):
    class FailingProvider:
        async def generate_structured(self, *_args, **_kwargs):
            raise LLMProviderError("unavailable", retry_count=1)

    monkeypatch.setattr("app.graph.nodes.get_llm_provider", lambda: FailingProvider())
    response = await chat.run_chat(ChatRequest(question="Kenapa sales Jawa Barat turun bulan ini?", language="id"))
    assert response.status == "ok"
    assert response.data.rows
    assert any("AI analysis was unavailable" in caveat for caveat in response.answer.caveats)
    assert "stockout" not in response.model_dump_json().lower()


@pytest.mark.asyncio
async def test_health_represents_remote_unknown_without_failing_application(monkeypatch):
    class RemoteProvider:
        async def health_check(self):
            return ModelHealth(mode="remote", status="unknown", provider="qwen_openai_compatible", model="Qwen3.8-27B-AWQ")

    monkeypatch.setattr(health_route, "get_settings", lambda: Settings(_env_file=None, llm_mode="remote"))
    monkeypatch.setattr(health_route, "get_llm_provider", lambda *_: RemoteProvider())
    result = await health_route.health()
    assert result.status == "ok"
    assert result.model_backend.mode == "remote"
    assert result.model_backend.status == "unknown"


@pytest.mark.asyncio
async def test_chat_telemetry_records_safe_model_status(monkeypatch):
    captured = {}
    monkeypatch.setattr(chat.telemetry, "record", lambda **event: captured.update(event))
    response = await chat.run_chat(ChatRequest(question="Berapa sales Jawa Barat bulan ini?", language="id"))
    assert response.status == "ok"
    model = captured["metadata"]["model"]
    assert model["provider"] == "mock"
    assert model["success"] is True
    assert "token" not in str(model).lower() or model.get("total_tokens") is None
