from __future__ import annotations

import pytest

from app.core.schemas import ChatRequest
from app.services import chat
from app.services.conversation_store import ConversationStore, MAX_HISTORY_MESSAGES


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Points ConversationStore at a throwaway file for this test only, and
    swaps out the module-level singleton chat.py actually uses."""
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(tmp_path / "conversation_history.sqlite"))
    from app.core.config import get_settings
    get_settings.cache_clear()
    store = ConversationStore()
    monkeypatch.setattr(chat, "conversations", store)
    yield store
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_multi_turn_conversation_persists_and_bounds_history(isolated_store):
    session_id = "test-multi-turn"
    questions = [
        "Kenapa sales Jawa Barat turun bulan ini?",
        "Bagaimana dengan produk Bodrex?",
        "ada gak data2 pendukung selain ini?",
    ]
    for question in questions:
        response = await chat.run_chat(ChatRequest(question=question, session_id=session_id))
        assert response.status in {"ok", "fallback"}

    history = isolated_store.load_history(session_id)
    # One user + one assistant message per turn, growing linearly - the
    # LangGraph checkpointer approach this replaced was observed to
    # duplicate history exponentially across turns instead.
    assert len(history) == len(questions) * 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == questions[0]
    assert history[-1]["role"] == "assistant"

    db_path = isolated_store.path
    assert db_path.is_file()
    assert db_path.stat().st_size < 1024 * 1024


def test_conversation_store_isolates_sessions(isolated_store):
    isolated_store.append_turn("session-a", "question a", "answer a")
    isolated_store.append_turn("session-b", "question b", "answer b")

    history_a = isolated_store.load_history("session-a")
    history_b = isolated_store.load_history("session-b")

    assert [m["content"] for m in history_a] == ["question a", "answer a"]
    assert [m["content"] for m in history_b] == ["question b", "answer b"]


def test_conversation_store_bounds_history_length(isolated_store):
    session_id = "long-session"
    num_turns = MAX_HISTORY_MESSAGES  # 2 messages per turn, so 2x MAX_HISTORY_MESSAGES total
    for i in range(num_turns):
        isolated_store.append_turn(session_id, f"question {i}", f"answer {i}")

    history = isolated_store.load_history(session_id)
    assert len(history) == MAX_HISTORY_MESSAGES
    # Oldest turns are dropped, most recent kept, in original (oldest-first) order.
    assert history[-1]["content"] == f"answer {num_turns - 1}"
    assert history[0]["role"] == "user"
