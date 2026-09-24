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
    assert service.status()["datasets"] == 14
    assert service.status()["metrics"] == 39


def test_resolve_official_gross_sales_metric() -> None:
    result = _service().resolve("Berapa Gross Sales selama Q4 2024?")
    assert result["status"] == "resolved"
    assert result["metric"] == "gross_billing_value"
    assert result["definition"]["metric_id"] == "SI-01"


def test_resolve_material_fill_rate_prefers_material_metric() -> None:
    result = _service().resolve("Material mana dengan Fill Rate terendah?")
    assert result["status"] == "resolved"
    assert result["metric"] == "material_fill_rate"


def test_resolve_sales_office_picking_metric() -> None:
    result = _service().resolve("Sales office mana dengan picking delay rate tertinggi?")
    assert result["status"] == "resolved"
    assert result["metric"] == "picking_delay_rate"


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


def test_compile_low_fill_filter_is_allowlisted() -> None:
    compiled = _service().compile_query(
        OssieQueryRequest(
            metric="service_fill_rate",
            dimensions=["material", "fill_rate_band"],
            filters={"fill_rate_band": ["low_fill"]},
        )
    )
    assert "d.fill_rate_band IN ('low_fill')" in compiled["sql"]


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

