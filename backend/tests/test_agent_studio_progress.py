from __future__ import annotations

from app.services import agent_studio_progress as progress


def test_task_started_maps_to_understanding_message() -> None:
    message = progress.stage_message({"type": "task_started"}, seen_data_retrieval=False)
    assert message == "Memahami pertanyaan kamu..."


def test_first_delegation_maps_to_contacting_data_team() -> None:
    event = {"type": "tool_usage_started", "tool_name": "Ask question to coworker"}
    message = progress.stage_message(event, seen_data_retrieval=False)
    assert message == "Menghubungi tim data TEMPO..."


def test_second_delegation_after_data_retrieval_maps_to_composing_answer() -> None:
    event = {"type": "tool_usage_started", "tool_name": "Ask question to coworker"}
    message = progress.stage_message(event, seen_data_retrieval=True)
    assert message == "Menyusun jawabannya..."


def test_resolve_semantic_object_maps_to_finding_metric() -> None:
    event = {"type": "tool_usage_started", "tool_name": "resolve semantic object"}
    assert progress.stage_message(event, seen_data_retrieval=False) == "Mencari metric yang paling sesuai..."


def test_execute_governed_query_maps_to_fetching_data() -> None:
    event = {"type": "tool_usage_started", "tool_name": "execute governed query"}
    assert progress.stage_message(event, seen_data_retrieval=False) == "Mengambil angka dari data governed..."
    assert progress.is_data_retrieval_stage(event) is True


def test_silent_event_types_produce_no_message() -> None:
    for event_type in ["llm_call_started", "llm_call_completed", "tool_usage_finished", "task_completed"]:
        assert progress.stage_message({"type": event_type}, seen_data_retrieval=False) is None


def test_unrecognized_event_produces_no_message() -> None:
    assert progress.stage_message({"type": "crew_kickoff_started"}, seen_data_retrieval=False) is None


def test_non_data_tool_is_not_a_data_retrieval_stage() -> None:
    event = {"type": "tool_usage_started", "tool_name": "resolve semantic object"}
    assert progress.is_data_retrieval_stage(event) is False
