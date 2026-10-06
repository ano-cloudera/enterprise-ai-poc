from app.services.conversational import (
    _is_analytic_escape_from_clarification,
    _is_sell_in_vs_sell_out_concept,
)


def test_detects_management_concept_question() -> None:
    q = "Halo, apa bedanya sell-in Tempo dan sell-out Alfamart untuk tim manajemen?"
    assert _is_sell_in_vs_sell_out_concept(q) is True


def test_does_not_hijack_analytic_ranking() -> None:
    q = "Top 10 sell-in Tempo vs sell-out Alfamart Q4 2024"
    assert _is_sell_in_vs_sell_out_concept(q) is False


def test_analytic_escape_after_clarification() -> None:
    q = "cukup tampilkan sell-in FE001 per bulan Q4"
    assert _is_analytic_escape_from_clarification(q) is True
