from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.schemas import ChatRequest
from app.services import agent_studio_client, chat
from app.services.conversation_store import ConversationStore


@pytest.fixture
def isolated_conversations(tmp_path, monkeypatch) -> ConversationStore:
    # A real ConversationStore against a throwaway SQLite file, not a mock
    # - the behavior under test is genuinely round-tripping through
    # load_history/append_turn, not just that they're called.
    store = ConversationStore.__new__(ConversationStore)
    store.path = tmp_path / "conversations.sqlite"
    store._init()
    monkeypatch.setattr(chat, "conversations", store)
    return store


def _agent_studio_settings() -> Settings:
    return Settings(chat_backend="agent_studio", agent_studio_base_url="https://example.com", agent_studio_api_key="test-key")


@pytest.mark.asyncio
async def test_first_question_sends_empty_context(isolated_conversations, monkeypatch) -> None:
    monkeypatch.setattr(chat, "get_settings", _agent_studio_settings)
    captured = {}

    async def fake_run_workflow(user_input: str, context: str = "") -> agent_studio_client.AgentStudioResult:
        captured["context"] = context
        return agent_studio_client.AgentStudioResult(trace_id="t1", output="### Jawaban\n\nGross Sales naik.")

    monkeypatch.setattr(agent_studio_client, "run_workflow", fake_run_workflow)
    request = ChatRequest(question="Berapa Gross Sales Q4 2024?", session_id="s1")

    await chat._run_chat_agent_studio(request)

    assert captured["context"] == ""


@pytest.mark.asyncio
async def test_follow_up_question_sends_the_previous_markdown_answer_as_context(isolated_conversations, monkeypatch) -> None:
    # Reproduces the real failure: Master Agent's Backstory expects a
    # FOLLOW_UP envelope built from the prior turn's context, but nothing
    # ever supplied one, so "breakdown per bulan?" got "saya belum
    # memiliki konteks pertanyaan sebelumnya" instead of being resolved.
    monkeypatch.setattr(chat, "get_settings", _agent_studio_settings)
    isolated_conversations.append_turn("s1", "Berapa Gross Sales Q4 2024?", "### Jawaban\n\nTotal Gross Sales Rp 3.8T untuk Q4 2024.")
    captured = {}

    async def fake_run_workflow(user_input: str, context: str = "") -> agent_studio_client.AgentStudioResult:
        captured["context"] = context
        return agent_studio_client.AgentStudioResult(trace_id="t2", output="### Breakdown\n\n...")

    monkeypatch.setattr(agent_studio_client, "run_workflow", fake_run_workflow)
    request = ChatRequest(question="bisa di bantu breakdown gak per bulan?", session_id="s1")

    await chat._run_chat_agent_studio(request)

    assert "Total Gross Sales Rp 3.8T untuk Q4 2024" in captured["context"]


@pytest.mark.asyncio
async def test_different_session_does_not_leak_context(isolated_conversations, monkeypatch) -> None:
    monkeypatch.setattr(chat, "get_settings", _agent_studio_settings)
    isolated_conversations.append_turn("s1", "Berapa Gross Sales Q4 2024?", "### Jawaban\n\nTotal Gross Sales Rp 3.8T.")
    captured = {}

    async def fake_run_workflow(user_input: str, context: str = "") -> agent_studio_client.AgentStudioResult:
        captured["context"] = context
        return agent_studio_client.AgentStudioResult(trace_id="t3", output="### Jawaban\n\n...")

    monkeypatch.setattr(agent_studio_client, "run_workflow", fake_run_workflow)
    request = ChatRequest(question="breakdown per bulan?", session_id="s2")

    await chat._run_chat_agent_studio(request)

    assert captured["context"] == ""


@pytest.mark.asyncio
async def test_answer_markdown_is_persisted_for_the_next_turn(isolated_conversations, monkeypatch) -> None:
    monkeypatch.setattr(chat, "get_settings", _agent_studio_settings)

    async def fake_run_workflow(user_input: str, context: str = "") -> agent_studio_client.AgentStudioResult:
        return agent_studio_client.AgentStudioResult(trace_id="t1", output="### Jawaban\n\nGross Sales naik 6.6%.")

    monkeypatch.setattr(agent_studio_client, "run_workflow", fake_run_workflow)
    request = ChatRequest(question="Berapa Gross Sales Q4 2024?", session_id="s1")

    await chat._run_chat_agent_studio(request)

    history = isolated_conversations.load_history("s1")
    assistant_turns = [turn["content"] for turn in history if turn["role"] == "assistant"]
    assert assistant_turns == ["### Jawaban\n\nGross Sales naik 6.6%."]
