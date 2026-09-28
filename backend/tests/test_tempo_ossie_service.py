from __future__ import annotations

import pytest

from app.core.config import Settings
from app.ossie.service import OssieQueryRequest, TempoOssieService


def _service(**overrides) -> TempoOssieService:
    return TempoOssieService(Settings(**overrides))


def test_ossie_service_is_enabled_by_default() -> None:
    service = _service()
    assert service.enabled is True
    assert service.status()["execution_mode"] == "ossie"
    assert service.status()["datasets"] == 19
    assert service.status()["metrics"] == 58


def test_resolve_official_gross_sales_metric() -> None:
    result = _service().resolve("Berapa Gross Sales selama Q4 2024?")
    assert result["status"] == "resolved"
    assert result["metric"] == "gross_billing_value"
    assert result["definition"]["metric_id"] == "SI-01"


def test_resolve_gross_sell_wording_to_official_revenue_metric() -> None:
    result = _service().resolve("berapa total gross sell 2024 q4 ?")
    assert result["status"] == "resolved"
    assert result["metric"] == "gross_billing_value"


def test_resolve_store_stock_by_dc_to_sat_idm_metric() -> None:
    result = _service().resolve(
        "DC mana yang memiliki stok store paling rendah selama Oktober sampai Desember 2024?"
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "sat_idm_store_stock_quantity"


def test_resolve_indonesian_oos_rate_wording() -> None:
    result = _service().resolve(
        "Material mana yang memiliki tingkat OOS tertinggi selama Q4 2024?"
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "sat_oos_rate"


def test_resolve_indonesian_stock_tempo_value_wording() -> None:
    result = _service().resolve(
        "Berapa total nilai Stock Tempo untuk masing-masing bulan selama Q4 2024?"
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "stock_tempo_value"
    assert result["definition"]["unit_format"] == "currency_idr"


@pytest.mark.parametrize(
    ("question", "expected_metric", "expected_id"),
    [
        (
            "Berapa total DO quantity per material Q4 2024?",
            "material_delivery_order_quantity",
            "SI-03-MAT",
        ),
        (
            "Berapa total DO amount per material Q4 2024?",
            "material_delivery_order_amount",
            "SI-04-MAT",
        ),
        (
            "Branch B2B mana dengan bill quantity tertinggi?",
            "b2b_branch_sell_out_quantity",
            "B2B-02-BR",
        ),
        (
            "PLU B2B mana dengan sell-out quantity tertinggi?",
            "b2b_material_plu_quantity",
            "B2B-03-PLU",
        ),
        (
            "Berapa nilai stok DC SAT-IDM per bulan?",
            "sat_idm_dc_stock_value",
            "SI-03-IDM",
        ),
        (
            "Berapa nilai stok store SAT-IDM per bulan?",
            "sat_idm_store_stock_value",
            "SI-04-IDM",
        ),
        (
            "Material mana dengan unfulfilled demand quantity terbesar?",
            "service_unfulfilled_quantity",
            "FL-02",
        ),
        (
            "Sales office mana dengan picking workload tertinggi?",
            "picking_workload_rows",
            "PK-04-Q4",
        ),
        (
            "Sales office mana dengan unloading events terbanyak?",
            "unloading_event_count",
            "UL-02-Q4",
        ),
    ],
)
def test_resolve_showcase_metric_extensions(
    question: str, expected_metric: str, expected_id: str
) -> None:
    result = _service().resolve(question)
    assert result["status"] == "resolved"
    assert result["metric"] == expected_metric
    assert result["definition"]["metric_id"] == expected_id


@pytest.mark.parametrize(
    ("question", "expected_metric"),
    [
        ("Berapa GBV Q4 2024?", "gross_billing_value"),
        ("Berapa gross sale Q4 2024?", "gross_billing_value"),
        ("Berapa billing qty Q4 2024?", "billing_quantity"),
        ("Berapa sell-in qty Q4 2024?", "billing_quantity"),
        ("Branch mana dengan B2B value tertinggi?", "b2b_branch_sell_out_value"),
        ("Branch mana dengan sellout tertinggi?", "b2b_branch_sell_out_value"),
        ("PLU mana dengan nilai B2B tertinggi?", "b2b_material_plu_value"),
        ("Berapa stok Tempo Q4 2024?", "stock_tempo_total_qty"),
        ("Berapa stock value Tempo?", "stock_tempo_value"),
        ("SKU mana dengan stok gudang terbesar?", "material_warehouse_stock_quantity"),
        ("DC mana dengan IDM stock terendah?", "sat_idm_dc_stock_quantity"),
        ("DC mana dengan dcstock terendah?", "sat_idm_dc_stock_quantity"),
        ("DC mana dengan storestock terendah?", "sat_idm_store_stock_quantity"),
        ("Material mana dengan OOS tertinggi?", "sat_oos_rate"),
        ("SKU mana paling sering OOS?", "sat_oos_rate"),
        ("PLU mana dengan out of stock tertinggi?", "sat_oos_rate"),
    ],
)
def test_resolve_common_five_domain_abbreviations(
    question: str, expected_metric: str
) -> None:
    result = _service().resolve(question)
    assert result["status"] == "resolved"
    assert result["metric"] == expected_metric


def test_generic_stock_question_still_requires_scope_clarification() -> None:
    result = _service().resolve("Berapa total stok Q4 2024?")
    assert result["status"] == "needs_clarification"
    assert result["reason"] == "stock_scope"


@pytest.mark.parametrize(
    "question",
    [
        "Berapa SO Q4 2024?",
        "Berapa SI Q4 2024?",
        "Berapa SL Q4 2024?",
    ],
)
def test_ambiguous_initialisms_are_not_guessed(question: str) -> None:
    result = _service().resolve(question)
    assert result["status"] == "unsupported"


def test_bare_dc_stock_still_requires_scope_clarification() -> None:
    result = _service().resolve("Berapa stok DC Q4 2024?")
    assert result["status"] == "needs_clarification"
    assert result["reason"] == "stock_scope"


@pytest.mark.parametrize(
    "question",
    [
        "Berapa total pipeline stok DC dan store SAT-IDM selama Q4 2024?",
        "Tolong jumlahkan dcstock dan storestock sebagai total stok SAT-IDM.",
        "Berapa gabungan nilai DC Stock dan Store Stock?",
    ],
)
def test_sat_idm_dc_and_store_are_never_combined_as_total_pipeline(
    question: str,
) -> None:
    result = _service().resolve(question)
    assert result["status"] == "needs_clarification"
    assert result["reason"] == "sat_idm_stock_level_aggregation"
    assert "tidak boleh dijumlahkan" in result["question"].lower()
    assert {option["metric"] for option in result["options"]} == {
        "sat_idm_dc_stock_quantity",
        "sat_idm_store_stock_quantity",
        "sat_idm_dc_stock_value",
        "sat_idm_store_stock_value",
    }


def test_resolve_material_fill_rate_prefers_material_metric() -> None:
    result = _service().resolve("Material mana dengan Fill Rate terendah?")
    assert result["status"] == "resolved"
    assert result["metric"] == "material_fill_rate"


def test_resolve_sales_office_picking_metric() -> None:
    result = _service().resolve("Sales office mana dengan picking delay rate tertinggi?")
    assert result["status"] == "resolved"
    assert result["metric"] == "picking_delay_rate"


@pytest.mark.parametrize(
    ("question", "expected_metric", "expected_dimension"),
    [
        (
            "Jumlah observasi promo per mekanisme Desember 2024",
            "promo_observation_count",
            "mekanisme",
        ),
        (
            "Berapa jumlah material SKU yang tercakup SAT Promo?",
            "promo_material_count",
            "reporting_month",
        ),
        (
            "Bagaimana distribusi kode program status Y X T?",
            "promo_observation_count",
            "program_status",
        ),
    ],
)
def test_resolve_safe_sat_promo_metrics(
    question: str, expected_metric: str, expected_dimension: str
) -> None:
    result = _service().resolve(question)
    assert result["status"] == "resolved"
    assert result["metric"] == expected_metric
    assert expected_dimension in result["definition"]["allowed_dimensions"]


def test_plain_active_promo_question_resolves_since_all_rows_are_confirmed_active() -> None:
    # Tempo confirmed 28 Sep 2026 (Pak Hieronimus Gunawan, WhatsApp,
    # replying to "Y = active kah?" with "abaikan saja pak, di list
    # tersebut, artinya aktif") that every row in the SAT Promo December
    # data is an active promo observation. A plain "promo aktif" question
    # is therefore answerable now - see promo_observation_count's
    # ai_context.instructions for the caveat that program_status still
    # does not distinguish active from inactive within that data.
    result = _service().resolve("Berapa jumlah promo aktif Desember 2024?")
    assert result["status"] == "resolved"
    assert result["metric"] == "promo_observation_count"


def test_inactive_promo_split_is_still_not_inferred_from_raw_program_status() -> None:
    # The Tempo confirmation only established "all rows are active" - it
    # never established a way to distinguish an inactive subset, so a
    # question implying that split must remain blocked.
    result = _service().resolve("Berapa jumlah promo tidak aktif Desember 2024?")
    assert result["status"] == "unsupported"


def test_ambiguous_sales_question_requires_clarification() -> None:
    result = _service().resolve("Berapa total penjualan?")
    assert result["status"] == "needs_clarification"
    assert result["reason"] == "sales_stage"


def test_compile_monthly_gross_sales_is_governed_and_unscaled() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="gross_billing_value",
            dimensions=["calmonth"],
            start_calmonth=202410,
            end_calmonth=202412,
        )
    )
    assert "FROM gold.rpt_sap_monthly_executive_semantic d" in compiled["sql"]
    assert "SUM(d.sales_bill_val)" in compiled["sql"]
    assert "* 100" not in compiled["sql"]
    assert "d.calmonth >= 202410" in compiled["sql"]
    assert "d.calmonth <= 202412" in compiled["sql"]
    assert compiled["semantic_plan"]["business_approval_status"] == (
        "pending_business_confirmation"
    )


def test_compile_material_metric_enforces_coverage_filter() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="material_warehouse_stock_quantity",
            dimensions=["material"],
            limit=25,
        )
    )
    assert "d.has_stock = TRUE" in compiled["sql"]
    assert "GROUP BY d.material" in compiled["sql"]
    assert compiled["sql"].endswith("LIMIT 25")


def test_compile_customer_reconciliation_enforces_shared_scope() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="sell_out_to_sell_in_value_ratio",
            dimensions=["customer"],
            start_calmonth=202410,
            end_calmonth=202412,
        )
    )
    assert "reconciliation_scope = 'shared_customer_only'" in compiled["sql"]
    assert "FROM gold.rpt_sap_customer_reconciliation_semantic d" in compiled["sql"]


def test_compile_sat_idm_q4_filter_uses_year_and_month_code_fields() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="sat_idm_store_stock_quantity",
            dimensions=["dcname"],
            start_calmonth=202410,
            end_calmonth=202412,
            order="asc",
            limit=10,
        )
    )
    assert "d.thn * 100 + CASE UPPER(d.bln)" in compiled["sql"]
    assert ">= 202410" in compiled["sql"]
    assert "<= 202412" in compiled["sql"]


def test_compile_sat_oos_q4_filter_uses_date_field() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="sat_oos_rate",
            dimensions=["material_code"],
            start_calmonth=202410,
            end_calmonth=202412,
            limit=10,
        )
    )
    assert "d.calmonth_date >= CAST('2024-10-01' AS DATE)" in compiled["sql"]
    assert "d.calmonth_date <= CAST('2024-12-01' AS DATE)" in compiled["sql"]


def test_compile_low_fill_filter_is_allowlisted() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="service_fill_rate",
            dimensions=["material", "fill_rate_band"],
            filters={"fill_rate_band": ["low_fill"]},
        )
    )
    assert "d.fill_rate_band IN ('low_fill')" in compiled["sql"]


def test_compile_material_do_amount_keeps_do_separate_from_official_revenue() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="material_delivery_order_amount",
            dimensions=["calmonth", "material"],
        )
    )
    assert "FROM gold.rpt_sap_material_month_semantic d" in compiled["sql"]
    assert "SUM(d.sales_do_amt) AS metric_value" in compiled["sql"]
    assert "sales_bill_val" not in compiled["sql"]
    assert "d.has_sell_in = TRUE" in compiled["sql"]


@pytest.mark.parametrize("dimension", ["branch", "sales_off"])
def test_compile_b2b_quantity_keeps_branch_and_sales_office_distinct(
    dimension: str,
) -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="b2b_branch_sell_out_quantity",
            dimensions=[dimension],
        )
    )
    assert "FROM gold.corr_b2b_branch_estore_month d" in compiled["sql"]
    assert f"d.{dimension} AS {dimension}" in compiled["sql"]
    assert f"GROUP BY d.{dimension}" in compiled["sql"]


def test_compile_service_unfulfilled_quantity_uses_aggregate_difference() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="service_unfulfilled_quantity",
            dimensions=["calmonth", "material"],
        )
    )
    assert (
        "SUM(d.service_po_qty) - SUM(d.service_do_qty) AS metric_value"
        in compiled["sql"]
    )


def test_compile_rejects_unpublished_dimension() -> None:
    with pytest.raises(ValueError, match="does not allow dimensions"):
        _service().compile_query(
            OssieQueryRequest(
                metric="gross_billing_value",
                dimensions=["customer"],
            )
        )


def test_execute_is_blocked_when_feature_flag_is_off() -> None:
    service = _service(semantic_execution_mode="legacy")
    with pytest.raises(RuntimeError, match="OSSIE_SEMANTIC_MODE_DISABLED"):
        service.execute_query(OssieQueryRequest(metric="gross_billing_value"))


def test_execute_requires_impala_even_when_ossie_enabled() -> None:
    service = _service(semantic_execution_mode="ossie", data_backend="duckdb")
    with pytest.raises(RuntimeError, match="OSSIE_REQUIRES_IMPALA_BACKEND"):
        service.execute_query(OssieQueryRequest(metric="gross_billing_value"))


@pytest.mark.asyncio
async def test_llm_fallback_is_not_invoked_when_deterministic_resolver_succeeds() -> None:
    # Verifies resolve_with_llm_fallback short-circuits on a deterministic
    # hit and never reaches the LLM path at all (mode="mock" here would
    # otherwise silently mask a bug that skips the deterministic result).
    result = await _service().resolve_with_llm_fallback("Berapa Gross Sales selama Q4 2024?")
    assert result["status"] == "resolved"
    assert result["metric"] == "gross_billing_value"
    assert result.get("resolved_by") != "llm_fallback"


@pytest.mark.asyncio
async def test_llm_fallback_preserves_deterministic_clarification(monkeypatch) -> None:
    from app.llm import factory as llm_factory

    def _unexpected_provider_call():
        raise AssertionError("LLM fallback must not override a governed clarification")

    monkeypatch.setattr(llm_factory, "get_llm_provider", _unexpected_provider_call)
    result = await _service().resolve_with_llm_fallback("Berapa total penjualan?")
    assert result["status"] == "needs_clarification"
    assert result["reason"] == "sales_stage"


@pytest.mark.asyncio
async def test_llm_fallback_returns_deterministic_unsupported_when_mock_finds_no_match() -> None:
    # llm_mode defaults to "mock", whose classify_metric always reports no
    # match (see MockLLMProvider.classify_metric) - the original
    # deterministic "unsupported" result must pass through unchanged.
    result = await _service().resolve_with_llm_fallback(
        "Pertanyaan yang benar-benar tidak ada hubungannya dengan metric manapun xyzzy"
    )
    assert result["status"] == "unsupported"


@pytest.mark.asyncio
async def test_llm_fallback_resolves_a_metric_the_deterministic_matcher_missed(monkeypatch) -> None:
    # Simulates the real-world gap this fallback exists for: a phrasing that
    # shares no token/substring with any registered synonym, so the
    # deterministic resolver returns "unsupported" even though a governed
    # metric genuinely answers the question - the LLM path should recover it.
    from app.llm import factory as llm_factory
    from app.llm.models import MetricClassification, MetricClassificationResult, ModelTelemetry

    service = _service()

    class _FakeMetricClassifierProvider:
        async def classify_metric(self, question, *, candidates, trace_id):
            names = {item["name"] for item in candidates}
            assert "sat_oos_rate" in names  # the closed list really is the governed catalog
            return MetricClassificationResult(
                classification=MetricClassification(metric_name="sat_oos_rate"),
                telemetry=ModelTelemetry(
                    trace_id=trace_id, provider="fake", model="fake", latency_ms=1,
                    retry_count=0, success=True, structured_validation_success=True,
                ),
            )

    monkeypatch.setattr(llm_factory, "get_llm_provider", lambda: _FakeMetricClassifierProvider())
    result = await service.resolve_with_llm_fallback(
        "Berapa persen survey toko yang mendapati produk habis di rak Desember 2024?"
    )
    assert result["status"] == "resolved"
    assert result["metric"] == "sat_oos_rate"
    assert result["resolved_by"] == "llm_fallback"
