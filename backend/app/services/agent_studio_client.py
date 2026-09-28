from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings


class AgentStudioError(RuntimeError):
    """Raised when the Agent Studio workflow can't be reached or times out.

    Callers (app/services/chat.py) catch this and fall back to
    ChatResponse(status="error") rather than letting it propagate — the
    same contract run_chat() already has for any other failure.
    """


@dataclass
class AgentStudioResult:
    trace_id: str
    output: str
    events: list[dict[str, Any]] = field(default_factory=list)


async def run_workflow(user_input: str, context: str = "") -> AgentStudioResult:
    """Create a session, kick off the workflow, and poll until it completes.

    Non-streaming convenience wrapper around stream_workflow() for callers
    that only want the final result (e.g. tests, or a future non-SSE
    caller) - drains the generator and keeps every event it yielded.
    """
    events: list[dict[str, Any]] = []
    trace_id = ""
    output = ""
    async for item in stream_workflow(user_input, context):
        if item["kind"] == "event":
            events.append(item["event"])
            trace_id = item["trace_id"]
        elif item["kind"] == "completed":
            return AgentStudioResult(trace_id=item["trace_id"], output=item["output"], events=events)
    # Only reached if stream_workflow's polling loop hit its deadline
    # without a crew_kickoff_completed event - mirrors the old
    # run_workflow's timeout behavior.
    raise AgentStudioError(
        f"Workflow did not complete within {get_settings().agent_studio_poll_timeout_seconds}s "
        f"(trace_id={trace_id})."
    )


async def stream_workflow(user_input: str, context: str = "") -> AsyncIterator[dict[str, Any]]:
    """Create a session, kick off the workflow, and yield progress as it
    happens - one dict per raw Agent Studio event as it's polled, plus a
    final {"kind": "completed", ...} item once crew_kickoff_completed
    appears. Powers the SSE route (app/api/routes/chat.py's /chat/stream)
    so the frontend can show real progress instead of a static spinner.

    Mirrors the exact REST contract validated manually against the
    Tempo-Scan-Intelligence-Prod deployment: createSession -> kickoff ->
    poll /workflow/events until a crew_kickoff_completed event appears.
    """
    settings = get_settings()
    base_url = settings.agent_studio_base_url.rstrip("/")
    if not base_url:
        raise AgentStudioError("AGENT_STUDIO_BASE_URL is not configured.")
    api_key = settings.agent_studio_api_key.get_secret_value()
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0) as client:
        try:
            session_response = await client.post("/api/workflow/createSession", json={})
            session_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentStudioError(f"createSession failed: {exc}") from exc

        try:
            kickoff_response = await client.post(
                "/api/workflow/kickoff",
                json={"inputs": {"user_input": user_input, "context": context}},
            )
            kickoff_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentStudioError(f"kickoff failed: {exc}") from exc

        trace_id = kickoff_response.json().get("trace_id")
        if not trace_id:
            raise AgentStudioError("kickoff response did not include a trace_id.")

        deadline = time.monotonic() + settings.agent_studio_poll_timeout_seconds
        while time.monotonic() < deadline:
            try:
                response = await client.get("/api/workflow/events", params={"trace_id": trace_id})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AgentStudioError(f"events poll failed: {exc}") from exc
            chunk = response.json().get("events", [])
            for event in chunk:
                yield {"kind": "event", "trace_id": trace_id, "event": event}
                if event.get("type") == "crew_kickoff_completed":
                    yield {"kind": "completed", "trace_id": trace_id, "output": event.get("output", "")}
                    return
            await asyncio.sleep(settings.agent_studio_poll_interval_seconds)
