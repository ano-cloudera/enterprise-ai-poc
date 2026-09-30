import pytest

from app.semantic.context import SemanticContextService


def test_context_is_derived_from_the_actual_tempo_ossie_contract() -> None:
    context = SemanticContextService()

    assert len(context.datasets) == 20
    assert len(context.metrics) == 62
    material = context.table_policy("gold.rpt_sap_material_month_semantic")
    assert "material" in material.columns
    assert "sell_in_bill_val" in material.columns
    assert material.domain == "material_360"


def test_context_compacts_only_approved_schema_without_credentials() -> None:
    context = SemanticContextService()

    payload = context.planner_context(["sales", "stock_tempo"])
    serialized = str(payload).lower()

    assert "gold.rpt_sap_material_month_semantic" in serialized
    assert "gold.corr_stock_tempo_month_seta" in serialized
    assert "password" not in serialized
    assert "api_key" not in serialized


def test_governed_compiler_uses_real_requested_dimensions() -> None:
    context = SemanticContextService()
    monthly = context.compile_governed("sat_idm_dc_stock_quantity", "Berapa quantity DC Stock per bulan?")
    division = context.compile_governed("sat_idm_store_stock_quantity", "Division mana dengan Store Stock tertinggi?")
    material = context.compile_governed("sat_oos_rate", "Material code mana dengan SAT OOS rate tertinggi?")

    assert "d.bln AS bln" in monthly
    assert "GROUP BY d.thn, d.bln" in monthly
    assert "d.division AS division" in division
    assert "GROUP BY d.division" in division
    assert "d.material_code AS material_code" in material
    assert "GROUP BY d.material_code" in material


@pytest.mark.parametrize("question", [
    "Produk mana dengan rasio stok Tempo terhadap penjualan sell-in paling tinggi?",
    "Produk mana dengan perbandingan stok Tempo dan sell-in paling tinggi?",
    "Branch mana dengan sell-out tinggi dibanding DC stock?",
    "PLU mana dengan store stock tinggi tetapi OOS juga tinggi?",
])
def test_multi_concept_paraphrase_cannot_use_a_partial_metric(question: str) -> None:
    resolution = SemanticContextService().resolve(question)

    if resolution["status"] == "resolved":
        assert any(token in resolution["metric"] for token in ("_to_", "_vs_"))
    else:
        assert resolution["status"] in {"fallback", "needs_clarification"}
