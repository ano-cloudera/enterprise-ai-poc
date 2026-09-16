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
async def test_deployment_readiness_reports_healthy_when_all_components_ok(monkeypatch):
    class ReachableAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def get(self, *_args, **_kwargs):
            class Response:
                status_code = 200
            return Response()

    monkeypatch.setattr(health_route.httpx, "AsyncClient", ReachableAsyncClient)
    result = await health_route.deployment_readiness()
    assert result.status == "healthy"
    names = {component.name for component in result.components}
    assert names == {"backend_api", "semantic_layer", "data_backend", "market_api", "llm_provider"}
    assert all(component.status == "healthy" for component in result.components)


@pytest.mark.asyncio
async def test_deployment_readiness_reports_unavailable_when_market_api_unreachable(monkeypatch):
    class UnreachableAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def get(self, *_args, **_kwargs):
            raise ConnectionError("refused")

    monkeypatch.setattr(health_route.httpx, "AsyncClient", UnreachableAsyncClient)
    result = await health_route.deployment_readiness()
    assert result.status == "unavailable"
    market = next(component for component in result.components if component.name == "market_api")
    assert market.status == "unavailable"
    assert "http://" not in market.detail
    assert result.model_dump_json().count("http://") == 0


@pytest.mark.asyncio
async def test_deployment_readiness_never_exposes_secrets(monkeypatch):
    monkeypatch.setattr(health_route, "get_settings", lambda: Settings(_env_file=None, llm_mode="remote", qwen_api_token="super-secret-token"))
    result = await health_route.deployment_readiness()
    payload = result.model_dump_json()
    assert "super-secret-token" not in payload


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
