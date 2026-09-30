from app.core.models import AnalysisOutput
from app.services.history import ConversationStore


def test_history_persists_provider_model_and_structured_answer(tmp_path) -> None:
    store = ConversationStore(tmp_path / "history.sqlite")
    answer = AnalysisOutput(
        direct_answer="10",
        executive_summary="Total is 10",
        insights=[],
        business_implications=[],
        caveats=[],
        data_reference="query result",
        chart_spec=None,
    )

    store.append("session-1", "question", answer, [{"value": 10}], None, "gemini", "gemini-model")

    history = store.load("session-1")
    assert history[0]["provider"] == "gemini"
    assert history[0]["model"] == "gemini-model"
    assert history[0]["answer"]["direct_answer"] == "10"
    assert "reasoning" not in str(history).lower()
