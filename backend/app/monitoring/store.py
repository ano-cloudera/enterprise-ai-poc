from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings


class TelemetryStore:
    def __init__(self) -> None:
        path = Path(get_settings().telemetry_db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._connect() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                question TEXT,
                intent TEXT,
                status TEXT,
                latency_ms INTEGER,
                validation_status TEXT,
                rows_returned INTEGER,
                metadata_json TEXT
                )"""
            )

    def record(self, **event) -> None:
        with self._connect() as con:
            con.execute(
                """INSERT INTO events(timestamp, trace_id, question, intent, status, latency_ms, validation_status, rows_returned, metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    event.get("trace_id", ""),
                    event.get("question", ""),
                    event.get("intent", ""),
                    event.get("status", ""),
                    int(event.get("latency_ms", 0)),
                    event.get("validation_status", ""),
                    int(event.get("rows_returned", 0)),
                    json.dumps(event.get("metadata", {})),
                ),
            )

    def summary(self) -> dict:
        with self._connect() as con:
            total = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            avg = con.execute("SELECT COALESCE(AVG(latency_ms),0) FROM events").fetchone()[0]
            success = con.execute("SELECT COUNT(*) FROM events WHERE status IN ('ok','fallback')").fetchone()[0]
            rejected = con.execute("SELECT COUNT(*) FROM events WHERE validation_status='rejected'").fetchone()[0]
            rows = con.execute("SELECT timestamp, question, intent, status, latency_ms FROM events ORDER BY id DESC LIMIT 8").fetchall()
        return {
            "total": total,
            "avg": round(avg or 0),
            "success_rate": round((success / total * 100) if total else 100.0, 1),
            "reject_rate": round((rejected / total * 100) if total else 0.0, 1),
            "recent": [
                {"timestamp": r[0], "question": r[1], "intent": r[2], "status": r[3], "latency_ms": r[4]} for r in rows
            ],
        }
