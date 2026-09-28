from __future__ import annotations

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.schemas import ChatMetadata, ChatResponse, DashboardState, ExecutiveAnswer, QueryData
from app.main import app


def _make_response() -> ChatResponse:
    return ChatResponse(
        status="ok",
        question="Berapa Gross Sales Q4 2024?",
        answer=ExecutiveAnswer(summary="Rp 3.8T", drivers=[], recommended_actions=[], caveats=[]),
        data=QueryData(),
        chart_spec=None,
        ui_actions=[],
        metadata=ChatMetadata(trace_id="t1", session_id="s1", intent="agent_studio", resolved_context=DashboardState(), execution_time_ms=1),
    )


def _parse_sse(body: str) -> list[dict]:
    frames = []
    for chunk in body.split("\n\n"):
        for line in chunk.split("\n"):
            if line.startswith("data: "):
                import json
                frames.append(json.loads(line[len("data: "):]))
    return frames


def test_stream_emits_progress_then_done() -> None:
    async def fake_stream(request):
        yield {"type": "progress", "label": "Memahami pertanyaan kamu..."}
        yield {"type": "done", "response": _make_response()}

    with patch("app.api.routes.chat.run_chat_stream", fake_stream):
        client = TestClient(app)
        response = client.post("/api/chat/stream", json={"question": "Berapa Gross Sales Q4 2024?", "session_id": "s1"})

    assert response.status_code == 200
    frames = _parse_sse(response.text)
    assert frames[0] == {"type": "progress", "label": "Memahami pertanyaan kamu..."}
    assert frames[1]["type"] == "done"
    assert frames[1]["response"]["answer"]["summary"] == "Rp 3.8T"


def test_stream_emits_heartbeat_comment_during_a_long_gap() -> None:
    async def slow_stream(request):
        await asyncio.sleep(0.2)
        yield {"type": "done", "response": _make_response()}

    with (
        patch("app.api.routes.chat.run_chat_stream", slow_stream),
        patch("app.api.routes.chat._HEARTBEAT_INTERVAL_SECONDS", 0.05),
    ):
        client = TestClient(app)
        response = client.post("/api/chat/stream", json={"question": "Berapa Gross Sales Q4 2024?", "session_id": "s1"})

    assert response.status_code == 200
    assert ": keep-alive\n\n" in response.text
    frames = _parse_sse(response.text)
    assert frames[-1]["type"] == "done"
