from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.core.config import Settings
from app.llm.factory import get_llm_provider
from app.llm.models import TrustedAnalysisPayload
from app.llm.payload import build_trusted_analysis_payload, deterministic_grounded_analysis
from app.llm.providers import LLMProviderError, MockLLMProvider, QwenOpenAICompatibleProvider
from app.semantic.loader import load_semantic_project
from app.semantic.resolver import normalize_analytical_intent, resolve_analytical_intent


VALID_ANALYSIS = {
    "summary": "Sales declined by 16.62%.",
    "drivers": [{"title": "Regional result", "description": "Jawa Barat declined.", "evidence": "percentage_change=-16.62"}],
    "recommended_actions": ["Review the governed result."],
    "caveats": [],
}


def settings(**overrides):
    values = {
        "llm_mode": "remote",
        "qwen_base_url": "https://qwen.example.test/v1",
        "qwen_model": "Qwen3.8-27B-AWQ",
        "qwen_api_token": "",
        "qwen_request_timeout_seconds": 1,
        "qwen_max_retries": 1,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def trusted_payload() -> TrustedAnalysisPayload:
    project = load_semantic_project("tempo_scan")
    intent = normalize_analytical_intent(
        resolve_analytical_intent("Kenapa sales Jawa Barat turun bulan ini?", {}, project), project
    )
    return build_trusted_analysis_payload(
        question="Kenapa sales Jawa Barat turun bulan ini?",
        language="id",
        intent=intent,
        rows=[{"region": "Jawa Barat", "current_value": 75_521, "previous_value": 90_575, "absolute_change": -15_054, "percentage_change": -16.62}],
        project=project,
    )


def response(content: str, status: int = 200, usage: dict | None = None):
    body = {"choices": [{"message": {"content": content}}]}
    if usage:
        body["usage"] = usage
    return httpx.Response(status, json=body)


def test_provider_selection_is_configuration_driven():
    assert isinstance(get_llm_provider(Settings(_env_file=None, llm_mode="mock")), MockLLMProvider)
    assert isinstance(get_llm_provider(settings()), QwenOpenAICompatibleProvider)


def test_qwen_configuration_comes_from_environment(monkeypatch):
    monkeypatch.setenv("QWEN_BASE_URL", "https://env-qwen.example/v1")
    monkeypatch.setenv("QWEN_API_TOKEN", "env-secret")
    configured = Settings(_env_file=None, llm_mode="remote")
    assert configured.qwen_base_url == "https://env-qwen.example/v1"
    assert configured.qwen_api_token.get_secret_value() == "env-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize("token,expects_auth", [("secret-token", True), ("", False)])
async def test_authorization_header_and_chat_completions_endpoint(token, expects_auth):
    captured = {}

    def handler(request: httpx.Request):
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        return response(json.dumps(VALID_ANALYSIS))

    provider = QwenOpenAICompatibleProvider(settings(qwen_api_token=token), transport=httpx.MockTransport(handler))
    await provider.generate_structured(trusted_payload(), language="id", trace_id="trace")
    assert captured["url"] == "https://qwen.example.test/v1/chat/completions"
    assert (captured["authorization"] == f"Bearer {token}") is expects_auth


@pytest.mark.asyncio
async def test_token_is_never_logged_on_authentication_failure(caplog):
    token = "never-log-this-token"
    provider = QwenOpenAICompatibleProvider(
        settings(qwen_api_token=token),
        transport=httpx.MockTransport(lambda _: response("{}", status=401)),
    )
    with caplog.at_level(logging.INFO), pytest.raises(LLMProviderError) as error:
        await provider.generate_structured(trusted_payload(), language="id", trace_id="trace")
    assert error.value.code == "auth_required"
    assert token not in caplog.text
    assert token not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected_code", [("timeout", "timeout"), ("connection", "unavailable")])
async def test_network_failures_are_safe_and_retry_only_once(failure, expected_code):
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("private internal detail", request=request)
        raise httpx.ConnectError("private internal detail", request=request)

    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError) as error:
        await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert error.value.code == expected_code
    assert error.value.retry_count == 1
    assert calls == 2
    assert "private internal detail" not in str(error.value)


@pytest.mark.asyncio
async def test_auth_failure_is_not_retried():
    calls = 0

    def handler(_: httpx.Request):
        nonlocal calls
        calls += 1
        return response("{}", status=403)

    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError) as error:
        await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert error.value.code == "auth_required"
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True])
async def test_valid_structured_response_and_markdown_json_are_accepted(wrapped):
    content = json.dumps(VALID_ANALYSIS)
    if wrapped:
        content = f"Result:\n```json\n{content}\n```"
    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(lambda _: response(content)))
    result = await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert result.analysis.summary == VALID_ANALYSIS["summary"]
    assert result.telemetry.structured_validation_success is True


@pytest.mark.asyncio
@pytest.mark.parametrize("first", ["not json", json.dumps({"summary": "missing fields"})])
async def test_invalid_json_or_schema_triggers_one_bounded_retry(first):
    calls = 0

    def handler(_: httpx.Request):
        nonlocal calls
        calls += 1
        return response(first if calls == 1 else json.dumps(VALID_ANALYSIS))

    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    result = await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert calls == 2
    assert result.telemetry.retry_count == 1


@pytest.mark.asyncio
async def test_unexpected_openai_response_schema_triggers_bounded_retry():
    calls = 0

    def handler(_: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={} if calls == 1 else {"choices": [{"message": {"content": json.dumps(VALID_ANALYSIS)}}]})

    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    result = await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert calls == 2
    assert result.telemetry.retry_count == 1


@pytest.mark.asyncio
async def test_failure_after_retry_is_safe():
    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(lambda _: response("not-json")))
    with pytest.raises(LLMProviderError) as error:
        await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert error.value.code == "invalid_response"
    assert error.value.retry_count == 1


@pytest.mark.asyncio
async def test_reasoning_tags_are_removed_before_parsing_and_never_returned():
    content = f"<think>secret reasoning</think>{json.dumps(VALID_ANALYSIS)}"
    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(lambda _: response(content)))
    result = await provider.generate_structured(trusted_payload(), language="en", trace_id="trace")
    assert "think" not in result.analysis.model_dump_json().lower()
    assert "secret reasoning" not in result.analysis.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(("language", "instruction"), [("id", "Bahasa Indonesia"), ("en", "English")])
async def test_prompt_respects_requested_language(language, instruction):
    captured = {}

    def handler(request: httpx.Request):
        captured.update(json.loads(request.content))
        return response(json.dumps(VALID_ANALYSIS))

    provider = QwenOpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    await provider.generate_structured(trusted_payload(), language=language, trace_id="trace")
    assert instruction in captured["messages"][0]["content"]


@pytest.mark.asyncio
async def test_model_receives_compact_trusted_payload_without_secrets_or_full_semantics():
    captured = {}

    def handler(request: httpx.Request):
        captured.update(json.loads(request.content))
        return response(json.dumps(VALID_ANALYSIS))

    provider = QwenOpenAICompatibleProvider(settings(qwen_api_token="top-secret"), transport=httpx.MockTransport(handler))
    await provider.generate_structured(trusted_payload(), language="id", trace_id="trace")
    serialized = json.dumps(captured)
    assert "current_value" in serialized and "percentage_change" in serialized
    assert "top-secret" not in serialized
    assert "allowed_questions" not in serialized
    assert "relationships" not in serialized
    assert "query_rules" not in serialized
    assert "sql" not in serialized.lower()


def test_deterministic_fallback_is_grounded_in_result_data():
    fallback = deterministic_grounded_analysis(trusted_payload(), provider_unavailable=True)
    serialized = fallback.model_dump_json()
    assert "Jawa Barat" in serialized and "-16.62" in serialized
    assert "stockout" not in serialized.lower()
    assert "AI analysis was unavailable" in serialized


def test_deterministic_analysis_infers_indonesian_when_language_is_auto():
    automatic = trusted_payload().model_copy(update={"language": "auto"})
    analysis = deterministic_grounded_analysis(automatic)
    assert analysis.summary.startswith("Nilai Jawa Barat berubah")


def test_deterministic_market_analysis_uses_business_labels_and_rounding():
    payload = TrustedAnalysisPayload(
        question="Strategi market share Bodrex",
        language="auto",
        intent={"intent_type": "market", "analysis_type": "share", "product_name": "Bodrex"},
        business_context={"calculated_metrics_immutable": True},
        query_result={
            "columns": ["product_name", "market_share_pct", "market_growth_pct", "avg_market_price", "opportunity_score"],
            "rows": [{
                "product_name": "Bodrex", "market_share_pct": 19.947109, "market_growth_pct": 2.898591,
                "avg_market_price": 527.6833, "opportunity_score": 66.3588,
            }],
        },
    )

    analysis = deterministic_grounded_analysis(payload)

    assert analysis.summary == "Bodrex memiliki pangsa pasar 19,9%, pertumbuhan pasar 2,9%, harga pasar rata-rata Rp528, dan skor peluang 66,4/100."
    assert "market_share_pct" not in analysis.summary


@pytest.mark.asyncio
async def test_usage_is_recorded_as_safe_model_telemetry():
    usage = {"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125}
    provider = QwenOpenAICompatibleProvider(settings(qwen_api_token="secret"), transport=httpx.MockTransport(lambda _: response(json.dumps(VALID_ANALYSIS), usage=usage)))
    result = await provider.generate_structured(trusted_payload(), language="en", trace_id="trace-123")
    dumped = result.telemetry.model_dump()
    assert dumped["provider"] == "qwen_openai_compatible"
    assert dumped["total_tokens"] == 125
    assert "secret" not in json.dumps(dumped)
