"""Translates raw Agent Studio workflow events into natural, user-facing
progress messages for the SSE stream (see app/api/routes/chat.py's
/chat/stream). Deliberately not a literal echo of tool/event names - a
user watching "Ask AI" should see something that reads like a person
working through the question, not an orchestration log.
"""
from __future__ import annotations

from typing import Any

_STAGE_MESSAGES: list[tuple[str, str | None, str]] = [
    # (event type, tool_name substring to match (None = any), message)
    ("task_started", None, "Memahami pertanyaan kamu..."),
    ("tool_usage_started", "resolve semantic object", "Mencari metric yang paling sesuai..."),
    ("tool_usage_started", "get metric definition", "Mengecek definisi resminya..."),
    ("tool_usage_started", "execute governed query", "Mengambil angka dari data governed..."),
    ("tool_usage_started", "execute_readonly_sql", "Mengambil data tambahan dari Impala..."),
    # "Ask question to coworker" fires twice in a typical run (Master->Data
    # Agent, then Master->Analysis Agent) - the second is distinguished by
    # already having produced at least one data-retrieval message.
    ("tool_usage_started", "Ask question to coworker", "Menghubungi tim data TEMPO..."),
]

_ANALYSIS_HANDOFF_MESSAGE = "Menyusun jawabannya..."
_FALLBACK_MESSAGE = "Masih menghitung, sebentar lagi..."

# Never surfaced to the user verbatim - these event types don't map to a
# new stage worth announcing (e.g. the "_finished" half of a tool call, or
# LLM call bookkeeping already implied by the surrounding stage message).
_SILENT_EVENT_TYPES = {"llm_call_started", "llm_call_completed", "tool_usage_finished", "task_completed"}


def stage_message(event: dict[str, Any], *, seen_data_retrieval: bool) -> str | None:
    """Returns a natural-language progress message for this event, or None
    if this event shouldn't produce a new message (e.g. a duplicate stage,
    or a bookkeeping event type in _SILENT_EVENT_TYPES).

    seen_data_retrieval tracks whether an "execute governed query" (or SQL
    fallback) stage has already fired in this run - used to tell the first
    "Ask question to coworker" (Master -> Data Agent) apart from the second
    (Master -> Analysis Agent), which reuses the same tool name.
    """
    event_type = event.get("type")
    if event_type in _SILENT_EVENT_TYPES:
        return None

    tool_name = (event.get("tool_name") or "").strip()

    if event_type == "tool_usage_started" and "ask question to coworker" in tool_name.lower():
        return _ANALYSIS_HANDOFF_MESSAGE if seen_data_retrieval else "Menghubungi tim data TEMPO..."

    for candidate_type, candidate_tool, message in _STAGE_MESSAGES:
        if event_type != candidate_type:
            continue
        if candidate_tool is not None and candidate_tool.lower() not in tool_name.lower():
            continue
        return message

    return None


def is_data_retrieval_stage(event: dict[str, Any]) -> bool:
    tool_name = (event.get("tool_name") or "").strip().lower()
    return event.get("type") == "tool_usage_started" and (
        "execute governed query" in tool_name or "execute_readonly_sql" in tool_name
    )


def fallback_message() -> str:
    return _FALLBACK_MESSAGE
