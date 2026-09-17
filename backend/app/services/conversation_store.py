from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path

from app.core.config import get_settings

# Kept well below the LLM prompt's practical context budget - long enough
# for real multi-turn follow-ups, short enough to bound both DB size per
# session and the tokens sent to the model each request.
MAX_HISTORY_MESSAGES = 20


class ConversationStore:
    """Persists chat history per session_id in plain SQLite - synchronous,
    one connection per call, no WAL/async machinery. A LangGraph SQLite
    checkpointer was tried first but was found to duplicate its `history`
    channel exponentially across turns (reducer applied against the full
    prior write log on every resume rather than once), ballooning a
    multi-turn conversation's checkpoint file to several GB within
    minutes - a correctness/version-compatibility issue in that dependency,
    not something to build around. This store owns exactly the data we
    need (session_id -> ordered list of {role, content}) with a bounded,
    predictable write pattern, and no cross-turn amplification is
    possible since each turn does exactly one INSERT."""

    def __init__(self) -> None:
        path = Path(get_settings().conversation_db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._connect() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
                )"""
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")

    def load_history(self, session_id: str, *, limit: int = MAX_HISTORY_MESSAGES) -> list[dict[str, str]]:
        """Most recent `limit` messages for this session, oldest first."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def append_turn(self, session_id: str, question: str, answer_summary: str) -> None:
        """Records exactly one turn (one user message, one assistant
        message) - called once per chat request, never in a loop, so
        growth is always linear in the number of turns actually asked."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                (session_id, question, now),
            )
            if answer_summary:
                con.execute(
                    "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                    (session_id, answer_summary, now),
                )
