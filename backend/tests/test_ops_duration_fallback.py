from app.services.ops_duration_narrative import deterministic_ops_duration_answer


def test_deterministic_picking_fastest_from_first_row() -> None:
    text = deterministic_ops_duration_answer(
        "Sales office mana picking-nya paling efisien (tercepat) Q4 2024?",
        "average_picking_minutes",
        [{"sales_office": "0274", "metric_value": 12.34}],
    )
    assert text is not None
    assert "0274" in text
    assert "12.34" in text


def test_deterministic_unloading_ignored_for_unrelated_metric() -> None:
    assert (
        deterministic_ops_duration_answer(
            "Sales office mana unloading-nya paling efisien?",
            "material_sell_in_value",
            [{"sales_office": "0201", "metric_value": 1}],
        )
        is None
    )
