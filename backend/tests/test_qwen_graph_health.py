from __future__ import annotations

import pytest

from app.api.routes import health as health_route
from app.core.config import Settings
from app.core.schemas import ChatRequest
from app.llm.models import ModelHealth
from app.ossie import graph_nodes as ossie_graph_nodes
from app.services import chat


class _FakeOssieRegistry:
    dataset_fields = {"monthly_executive": {"calmonth": {}}}


class _FakeOssieService:
    registry = _FakeOssieRegistry()

    def resolve(self, _question):
        return {
            "status": "resolved",
            "metric": "gross_billing_value",
            "definition": {
                "description": "Official Gross Billing Value",
                "metric_id": "SI-01",
                "allowed_dimensions": ["calmonth"],
                "base_dataset": "monthly_executive",
                "business_approval_status": "pending_business_confirmation",
                "governance_status": "approved_candidate",
                "ai_context": {},
            },
        }

    async def resolve_with_llm_fallback(self, question, *, trace_id=""):
        return self.resolve(question)

    def execute_query(self, request, trace_id=""):
        return {
            "sql": "SELECT calmonth, SUM(bill_val) FROM gold.view GROUP BY calmonth",
            "rows": [{"calmonth": 202410, "metric_value": 100.0}],
            "semantic_plan": {"source_view": "gold.rpt_sap_monthly_executive_semantic", "grain": "calmonth"},
            "telemetry": {"data_backend": "impala", "success": True},
        }


@pytest.mark.asyncio
async def test_ossie_question_returns_governed_answer(monkeypatch):
    monkeypatch.setattr(ossie_graph_nodes, "get_tempo_ossie_service", lambda: _FakeOssieService())
    response = await chat.run_chat(ChatRequest(question="Berapa Gross Sales Q4 2024?", language="id"))
    assert response.status == "ok"
    assert response.data.rows
    assert response.metadata.intent == "ossie_analytical"


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
    # market_api is only probed in legacy mode (see deployment_readiness);
    # OSSIE is the default now, and it doesn't depend on the Mock Market API.
    assert names == {"backend_api", "semantic_layer", "data_backend", "llm_provider"}
    assert all(component.status == "healthy" for component in result.components)


@pytest.mark.asyncio
async def test_deployment_readiness_reports_agent_studio_as_degraded_not_unavailable_when_unprovisioned(monkeypatch):
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

    class LiteLLMProviderStub:
        async def health_check(self):
            return ModelHealth(mode="remote", status="ok", provider="litellm", model="commercial-intelligence")

    monkeypatch.setattr(health_route.httpx, "AsyncClient", ReachableAsyncClient)
    monkeypatch.setattr(health_route, "get_settings", lambda: Settings(_env_file=None, llm_mode="remote", litellm_base_url="https://litellm.example.test"))
    monkeypatch.setattr(health_route, "get_llm_provider", lambda *_: LiteLLMProviderStub())
    result = await health_route.deployment_readiness()

    components = {component.name: component for component in result.components}
    assert components["llm_provider"].status == "healthy"
    assert components["agent_studio_workflow"].status == "degraded"
    assert "not provisioned" in components["agent_studio_workflow"].detail.lower()
    # Agent Studio not being provisioned yet is expected, not a failure -
    # it must not drag the overall deployment status down.
    assert result.status == "healthy"


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

    # market_api is only probed in legacy mode (see deployment_readiness).
    monkeypatch.setattr(health_route, "get_settings", lambda: Settings(_env_file=None, semantic_execution_mode="legacy", project_id="tempo_scan"))
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
    # ossie_analytical is a deterministic governed compiler (no LLM call),
    # so telemetry comes from data_telemetry rather than model_telemetry -
    # this still checks the same thing: nothing secret leaks into telemetry.
    monkeypatch.setattr(ossie_graph_nodes, "get_tempo_ossie_service", lambda: _FakeOssieService())
    captured = {}
    monkeypatch.setattr(chat.telemetry, "record", lambda **event: captured.update(event))
    response = await chat.run_chat(ChatRequest(question="Berapa Gross Sales Q4 2024?", language="id"))
    assert response.status == "ok"
    data = captured["metadata"]["data"]
    assert data["success"] is True
    assert "token" not in str(data).lower()
