from app.core.models import AnalysisOutput
from app.services.chat import contextualize_question
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


def test_short_sell_in_follow_up_reuses_the_previous_question() -> None:
    history = [
        {
            "question": "Kalau jumlah penjualan selama Q4 berapa besar?",
            "answer": {"direct_answer": "Mau Sell-In atau Sell-Out?"},
        }
    ]

    contextualized = contextualize_question("untuk data sell-in ya", history)

    assert "Kalau jumlah penjualan selama Q4 berapa besar?" in contextualized
    assert "sell-in" in contextualized.casefold()


def test_standalone_question_is_not_rewritten_from_history() -> None:
    history = [{"question": "Berapa total penjualan?", "answer": {"direct_answer": "Sell-In atau Sell-Out?"}}]

    assert contextualize_question("Top 5 produk dengan gross sales terbesar", history) == "Top 5 produk dengan gross sales terbesar"
