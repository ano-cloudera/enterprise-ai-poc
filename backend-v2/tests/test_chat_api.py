from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.models import AnalysisOutput, AskDataResponse, QueryData, Timings
from app.db.base import DataBackendError
from app.main import create_app
from app.api import chat as chat_api
from app.llm.base import ProviderError
from app.services.chat import ChatService, ImpalaQueryExecutor


class FakeChatService:
    async def run(self, request):
        return AskDataResponse(
            request_id="request-1",
            session_id=request.session_id,
            status="SUCCESS",
            provider=request.provider,
            model=request.model,
            strategy="governed",
            answer=AnalysisOutput(direct_answer="10", executive_summary="Total 10", insights=[], business_implications=[], caveats=[], data_reference="result", chart_spec=None),
            data=QueryData(columns=["value"], rows=[{"value": 10}], row_count=1, execution_ms=1),
            chart_spec=None,
            timings=Timings(total_ms=2),
        )

    async def stream(self, request):
        for stage in ("understanding_request", "retrieving_context", "preparing_query", "validating_query", "querying_data", "analyzing_result"):
            yield {"type": "progress", "stage": stage, "label": stage.replace("_", " ").title()}
        yield {"type": "done", "response": await self.run(request)}


def client() -> TestClient:
    app = create_app(Settings(_env_file=None, qwen_base_url="https://qwen", qwen_api_key="token", qwen_model="qwen-model"))
    app.state.chat_service = FakeChatService()
    return TestClient(app)


def test_chat_rejects_model_not_exposed_by_backend() -> None:
    response = client().post("/chat", json={"session_id": "s", "question": "q", "provider": "qwen", "model": "arbitrary"})
    assert response.status_code == 422
    assert "not configured" in response.text


def test_chat_stream_emits_progress_and_terminal_response() -> None:
    response = client().post("/chat/stream", json={"session_id": "s", "question": "q", "provider": "qwen", "model": "qwen-model"})
    assert response.status_code == 200
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [frame["stage"] for frame in frames if frame["type"] == "progress"] == [
        "understanding_request", "retrieving_context", "preparing_query", "validating_query", "querying_data", "analyzing_result"
    ]
    assert frames[-1]["type"] == "done"
    assert frames[-1]["response"]["status"] == "SUCCESS"
    assert response.headers["x-accel-buffering"] == "no"


def test_chat_stream_heartbeat_does_not_cancel_slow_terminal_response(monkeypatch) -> None:
    class SlowChatService(FakeChatService):
        async def stream(self, request):
            await asyncio.sleep(0.03)
            yield {"type": "done", "response": await self.run(request)}

    test_client = client()
    test_client.app.state.chat_service = SlowChatService()
    monkeypatch.setattr(chat_api, "HEARTBEAT_SECONDS", 0.005)

    response = test_client.post("/chat/stream", json={"session_id": "s", "question": "q", "provider": "qwen", "model": "qwen-model"})

    assert ": keep-alive" in response.text
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert frames[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_impala_executor_does_not_block_the_event_loop() -> None:
    executor = ImpalaQueryExecutor(Settings(_env_file=None))

    class SlowBackend:
        def execute(self, *_):
            time.sleep(0.03)
            return SimpleNamespace(
                columns=[SimpleNamespace(name="value")],
                records=lambda: [{"value": 1}],
                row_count=1,
                telemetry=SimpleNamespace(query_latency_ms=30),
            )

    executor.backend = SlowBackend()
    task = asyncio.create_task(executor.execute("SELECT 1", "request-1"))
    await asyncio.sleep(0.005)

    assert not task.done()
    assert (await task)["rows"] == [{"value": 1}]


@pytest.mark.asyncio
async def test_chat_reports_impala_auth_failure_without_exposing_driver_details() -> None:
    class FailedWorkflow:
        async def ainvoke(self, _initial):
            raise DataBackendError("IMPALA_AUTH_FAILED")

    class EmptyHistory:
        def load(self, *_args, **_kwargs):
            return []

    class FailingProvider:
        async def generate_structured(self, *_args, **_kwargs):
            raise ProviderError("PROVIDER_ERROR")

    class FakeRegistry:
        def resolve(self, *_args, **_kwargs):
            return FailingProvider()

    service = object.__new__(ChatService)
    service.workflow = FailedWorkflow()
    service.history = EmptyHistory()
    service.settings = Settings(_env_file=None)
    service.dependencies = SimpleNamespace(provider_registry=FakeRegistry())
    request = SimpleNamespace(
        session_id="session-1",
        question="Berapa fill rate?",
        provider="qwen",
        model="qwen-model",
        model_dump=lambda: {
            "session_id": "session-1",
            "question": "Berapa fill rate?",
            "provider": "qwen",
            "model": "qwen-model",
        },
    )

    response = await service.run(request)

    assert response.status == "ERROR"
    assert "impala" in response.answer.direct_answer.casefold() or "autentikasi" in response.answer.direct_answer.casefold()
    assert any(response.request_id in caveat for caveat in response.answer.caveats)
    assert "Internal error details" not in " ".join(response.answer.caveats)
