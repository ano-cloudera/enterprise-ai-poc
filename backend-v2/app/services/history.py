from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.core.models import AnalysisOutput, ChartSpec


class ConversationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    rows_json TEXT NOT NULL,
                    chart_json TEXT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def append(self, session_id: str, question: str, answer: AnalysisOutput, rows: list[dict], chart: ChartSpec | None, provider: str, model: str) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO messages(session_id,question,answer_json,rows_json,chart_json,provider,model) VALUES(?,?,?,?,?,?,?)",
                (session_id, question, answer.model_dump_json(), json.dumps(rows, default=str), chart.model_dump_json() if chart else None, provider, model),
            )

    def load(self, session_id: str, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT question,answer_json,rows_json,chart_json,provider,model,created_at FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            {"question": row[0], "answer": json.loads(row[1]), "rows": json.loads(row[2]), "chart_spec": json.loads(row[3]) if row[3] else None, "provider": row[4], "model": row[5], "timestamp": row[6]}
            for row in reversed(rows)
        ]
