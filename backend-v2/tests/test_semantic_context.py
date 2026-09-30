import pytest

from app.semantic.context import SemanticContextService
from app.services.chat import contextualize_question


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


def test_dataset_name_scopes_context_to_only_that_dataset() -> None:
    context = SemanticContextService()

    payload = context.planner_context(["monthly_executive"])

    assert [dataset["name"] for dataset in payload["datasets"]] == ["monthly_executive"]
    assert payload["metrics"]
    assert {metric["dataset"] for metric in payload["metrics"]} == {"monthly_executive"}


def test_top_products_gross_sales_uses_governed_material_metric() -> None:
    context = SemanticContextService()

    resolution = context.resolve("Bisa bantu cek berapa gross sales untuk top 5 produk?")
    sql = context.compile_governed(
        resolution["metric"],
        "Bisa bantu cek berapa gross sales untuk top 5 produk?",
        resolution.get("dimensions"),
    )

    assert resolution["status"] == "resolved"
    assert resolution["metric"] == "material_sell_in_value"
    assert resolution["dimensions"] == ["material"]
    assert "d.has_sell_in = TRUE" in sql
    assert "GROUP BY d.material" in sql
    assert "ORDER BY metric_value DESC" in sql
    assert "LIMIT 5" in sql


@pytest.mark.parametrize("reply", ["sell in", "penjualan tempo ke customer"])
def test_sell_in_clarification_keeps_top_product_grain(reply: str) -> None:
    history = [{
        "question": "Berapa total produk dengan penjualan terbanyak, kasih top 5 saja?",
        "answer": {"direct_answer": "Pilih Sell-In (penjualan Tempo ke customer) atau Sell-Out?"},
    }]

    contextualized = contextualize_question(reply, history)
    context = SemanticContextService()
    resolution = context.resolve(contextualized)
    sql = context.compile_governed(resolution["metric"], contextualized, resolution["dimensions"])

    assert resolution["metric"] == "material_sell_in_value"
    assert resolution["dimensions"] == ["material"]
    assert "LIMIT 5" in sql


def test_stock_guidance_uses_governed_metric_knowledge_and_examples() -> None:
    context = SemanticContextService()

    guidance = context.guidance_context("Saya mau tahu data stok bisa apa saja?")

    metric_names = {metric["name"] for metric in guidance["metrics"]}
    assert guidance["focus"] == "stock"
    assert "stock_tempo_total_qty" in metric_names
    assert "sat_idm_store_stock_quantity" in metric_names
    assert any("stok" in example.casefold() or "stock" in example.casefold() for example in guidance["examples"])


def test_retail_stock_choice_resolves_without_repeating_clarification() -> None:
    resolution = SemanticContextService().resolve("stok retail")

    assert resolution["status"] == "resolved"
    assert resolution["metric"] == "sat_idm_store_stock_quantity"


@pytest.mark.parametrize("question", [
    "Stok di DC partner sekarang berapa ya per PLU?",
    "DC mana yang stoknya paling kecil bulan ini?",
    "DC partner",
    "DC partner mana paling rendah bulan ini?",
])
def test_explicit_partner_dc_stock_scope_does_not_repeat_clarification(question: str) -> None:
    resolution = SemanticContextService().resolve(question)

    assert resolution["status"] == "resolved"
    assert resolution["metric"] == "sat_idm_dc_stock_quantity"


def test_current_partner_dc_stock_ranking_uses_latest_snapshot_and_top_ten() -> None:
    context = SemanticContextService()
    question = "DC mana yang stoknya paling kecil bulan ini?"
    resolution = context.resolve(question)
    sql = context.compile_governed(resolution["metric"], question, resolution.get("dimensions"))

    assert "d.dcname AS dcname" in sql
    assert "d.thn = 2024" in sql
    assert "d.bln = 'DEC'" in sql
    assert "ORDER BY metric_value ASC" in sql
    assert "LIMIT 10" in sql


def test_stock_rankings_are_capped_at_top_ten() -> None:
    context = SemanticContextService()

    default_sql = context.compile_governed(
        "sat_idm_dc_stock_quantity",
        "PLU mana yang stok DC partner paling tinggi?",
    )
    oversized_sql = context.compile_governed(
        "sat_idm_store_stock_quantity",
        "Tampilkan top 50 PLU dengan stok toko tertinggi",
    )

    assert "LIMIT 10" in default_sql
    assert "LIMIT 10" in oversized_sql


@pytest.mark.parametrize("question", [
    "Coba jumlahin total stok DC sama stok toko, jadi berapa total pipeline kita?",
    "Jumlahkan stock DC dengan stok di toko",
    "jumlah stok DC dan toko",
    "total persediaan DC partner dan toko",
    "gabungkan persediaan distribution center dan store",
])
def test_dc_and_toko_stock_cannot_be_added_as_total_pipeline(question: str) -> None:
    resolution = SemanticContextService().resolve(question)

    assert resolution["status"] == "needs_clarification"
    assert resolution["reason"] == "sat_idm_stock_level_aggregation"


@pytest.mark.parametrize("question", [
    "store mana yang stoknya paling rendah bulan ini?",
    "toko",
    "toko mana paling rendah bulan ini?",
])
def test_explicit_store_scope_resolves_without_repeating_clarification(question: str) -> None:
    resolution = SemanticContextService().resolve(question)

    assert resolution["status"] == "resolved"
    assert resolution["metric"] == "sat_idm_store_stock_quantity"


def test_what_else_question_marks_sales_as_excluded_instead_of_focus() -> None:
    guidance = SemanticContextService().guidance_context("Bisa bantu apa lagi selain data sales?")

    assert guidance["focus"] is None
    assert guidance["excluded_focus"] == "sales"
    assert guidance["metrics"] == []


def test_broad_guidance_offers_cross_domain_governed_examples() -> None:
    guidance = SemanticContextService().guidance_context("Halo, bisa bantu apa?")

    options = {option["name"]: option for option in guidance["domain_options"]}
    assert len(options) == 9
    assert options["Stock SAT-IDM"]["metrics"] == [
        "sat_idm_dc_stock_quantity",
        "sat_idm_store_stock_quantity",
    ]
    assert options["Picking"]["examples"]
    assert options["SAT Promo"]["examples"]


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


@pytest.mark.parametrize(("question", "dimensions"), [
    ("Berapa persen toko yang kosong stoknya pas disurvei bulan lalu?", []),
    ("Material apa yang paling sering kosong di rak?", ["material_code"]),
    ("Customer/toko mana yang paling sering ngalamin stok kosong?", ["cust_id", "cust_code"]),
])
def test_natural_sat_oos_questions_route_to_oos_metric(question: str, dimensions: list[str]) -> None:
    resolution = SemanticContextService().resolve(question)

    assert resolution["status"] == "resolved"
    assert resolution["metric"] == "sat_oos_rate"
    assert resolution["dimensions"] == dimensions


def test_natural_sat_oos_last_month_uses_latest_governed_month() -> None:
    context = SemanticContextService()
    question = "Berapa persen toko yang kosong stoknya pas disurvei bulan lalu?"
    resolution = context.resolve(question)

    sql = context.compile_governed(resolution["metric"], question, resolution["dimensions"])

    assert "d.calmonth_date = CAST('2024-12-01' AS DATE)" in sql


def test_oos_sales_causality_is_rejected_instead_of_redirected_to_sales() -> None:
    resolution = SemanticContextService().resolve(
        "OOS ini pengaruh ke penurunan sales berapa besar sih?"
    )

    assert resolution["status"] == "unsupported"
    assert resolution["reason"] == "oos_sales_causality_unavailable"


@pytest.mark.parametrize(("question", "metric", "dimensions"), [
    ("Fill rate kita sekarang berapa secara keseluruhan?", "company_fill_rate", []),
    ("Material apa yang fill rate-nya paling jelek?", "material_fill_rate", ["material"]),
    ("Sales office mana yang fill rate-nya paling rendah?", "sales_office_service_fill_rate", ["sales_off"]),
    ("Ada gap gak antara PO yang masuk sama DO yang kekirim?", "service_unfulfilled_quantity", []),
])
def test_service_level_uat_questions_use_published_metrics(
    question: str, metric: str, dimensions: list[str]
) -> None:
    resolution = SemanticContextService().resolve(question)

    assert resolution["status"] == "resolved"
    assert resolution["metric"] == metric
    assert resolution.get("dimensions", []) == dimensions
