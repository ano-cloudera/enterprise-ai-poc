import pytest

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


def test_eight_word_uat_question_is_not_rewritten_after_long_prior_answer() -> None:
    history = [
        {
            "question": "Analisa data unloading dan picking dan berikan Analisa dan perbandingan dengan Industri standard",
            "answer": {
                "direct_answer": (
                    "Analisis unloading/picking Q4. Apakah Anda ingin detail per sales office?"
                ),
            },
        }
    ]
    reply = "Top 10 produk dengan penjualan terbesar di Tempo"
    assert contextualize_question(reply, history) == reply


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


@pytest.mark.parametrize("reply", ["data sellout", "data sell out", "Sell-Out", "sell-out aja"])
def test_sell_out_clarification_replies_all_merge_with_the_prior_question(reply: str) -> None:
    history = [
        {
            "question": "Top 10 DC Alfamart dengan penjualan tertinggi",
            "answer": {
                "direct_answer": (
                    "Apakah Anda ingin melihat Sell-In (penjualan Tempo ke customer) "
                    "atau Sell-Out (penjualan partner ke konsumen akhir)?"
                ),
            },
        }
    ]

    contextualized = contextualize_question(reply, history)

    assert contextualized == (
        "Top 10 DC Alfamart dengan penjualan tertinggi\n"
        "Klarifikasi pengguna: sell-out"
    )


def test_plain_sell_in_choice_preserves_the_original_top_product_request() -> None:
    history = [
        {
            "question": "Berapa total produk dengan penjualan terbanyak, kasih top 5 saja?",
            "answer": {
                "direct_answer": "Apakah Anda ingin melihat Sell-In (penjualan Tempo ke customer) atau Sell-Out?",
            },
        }
    ]

    contextualized = contextualize_question("sell in", history)

    assert contextualized == (
        "Berapa total produk dengan penjualan terbanyak, kasih top 5 saja?\n"
        "Klarifikasi pengguna: sell-in"
    )


def test_descriptive_sell_in_choice_does_not_add_customer_as_a_dimension() -> None:
    history = [
        {
            "question": "Berapa total produk dengan penjualan terbanyak, kasih top 5 saja?",
            "answer": {
                "direct_answer": "Apakah Anda ingin melihat Sell-In (penjualan Tempo ke customer) atau Sell-Out?",
            },
        }
    ]

    contextualized = contextualize_question("penjualan tempo ke customer", history)

    assert contextualized.endswith("Klarifikasi pengguna: sell-in")
    assert "customer" not in contextualized.casefold()


def test_standalone_question_is_not_rewritten_from_history() -> None:
    history = [{"question": "Berapa total penjualan?", "answer": {"direct_answer": "Sell-In atau Sell-Out?"}}]

    assert contextualize_question("Top 5 produk dengan gross sales terbesar", history) == "Top 5 produk dengan gross sales terbesar"


def test_unrelated_new_question_after_roi_promo_clarification_is_not_rewritten() -> None:
    # The ROI-promo proxy clarification is a long paragraph that happens to
    # share common domain words ("penjualan", "Tempo") with almost any new
    # question - a brand-new, unrelated topic must not be misread as the
    # user answering the ROI clarification just because of that overlap.
    history = [
        {
            "question": "Hitung promo dengan ROI terbaik dan berikan rekomendasi/ saran",
            "answer": {
                "direct_answer": (
                    "TEMPO tidak memiliki data biaya promo atau ROI langsung untuk SAT Promo "
                    "(Alfamart) - data yang tersedia hanya deskripsi mekanisme promo (teks bebas), "
                    "bukan nilai biaya terstruktur, dan SAT Promo hanya mencakup Desember 2024 tanpa "
                    "baseline bulan sebelumnya di channel yang sama. Satu-satunya proxy yang bisa "
                    "dihitung adalah dampak penjualan General Trade (bukan Alfamart langsung) untuk "
                    "material yang sama, dibandingkan November (baseline) vs Desember (bulan promo). "
                    "Metrik mana yang Anda mau?"
                ),
                "executive_summary": "",
                "insights": [],
            },
        }
    ]

    reply = "Top 10 produk dengan penjualan terbesar di Tempo"
    assert contextualize_question(reply, history) == reply


def test_unrelated_new_question_after_sales_stage_clarification_is_not_rewritten() -> None:
    history = [
        {
            "question": "berapa penjualan bulan ini?",
            "answer": {
                "direct_answer": (
                    "Apakah Anda ingin melihat Sell-In (penjualan Tempo ke customer) atau "
                    "Sell-Out (penjualan partner ke konsumen akhir)?"
                ),
            },
        }
    ]

    reply = "stok gudang tempo berapa banyak"
    assert contextualize_question(reply, history) == reply


def test_short_answer_to_stock_clarification_reuses_previous_question() -> None:
    history = [
        {
            "question": "Mau tahu tentang data stok, bisa analisis apa saja?",
            "answer": {"direct_answer": "Mau stok gudang Tempo, stok DC partner, atau stok retail?"},
        }
    ]

    contextualized = contextualize_question("stok retail", history)

    assert "Mau tahu tentang data stok" in contextualized
    assert "Klarifikasi pengguna: stok retail" in contextualized


def test_domain_choice_can_be_found_in_executive_summary() -> None:
    history = [
        {
            "question": "Data stok bisa dipakai untuk analisis apa?",
            "answer": {
                "direct_answer": "Ada beberapa arah analisis stok yang tersedia.",
                "executive_summary": "Pilih stok gudang Tempo, DC partner, atau retail store.",
                "insights": ["Contoh: stok retail per division."],
            },
        }
    ]

    contextualized = contextualize_question("stok retail", history)

    assert contextualized.endswith("Klarifikasi pengguna: stok retail")
