from __future__ import annotations

import json
import logging
import re
import time
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.models import (
    AnalysisResult,
    IntentClassification,
    IntentClassificationResult,
    ModelHealth,
    ModelTelemetry,
    StructuredAnalysis,
    TrustedAnalysisPayload,
)
from app.llm.payload import deterministic_grounded_analysis


logger = logging.getLogger(__name__)


class LLMProviderError(RuntimeError):
    def __init__(self, code: str, *, retry_count: int = 0, http_status: int | None = None, latency_ms: int = 0):
        self.code = code
        self.retry_count = retry_count
        self.http_status = http_status
        self.latency_ms = latency_ms
        super().__init__(f"Qwen analysis failed safely ({code})")


class LLMProvider(Protocol):
    async def generate_structured(self, payload: TrustedAnalysisPayload, *, language: str, trace_id: str) -> AnalysisResult: ...
    async def classify_intent(self, question: str, *, conversation_history: list[dict[str, str]], trace_id: str) -> IntentClassificationResult: ...
    async def health_check(self) -> ModelHealth: ...


class MockLLMProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_structured(self, payload: TrustedAnalysisPayload, *, language: str, trace_id: str) -> AnalysisResult:
        started = time.perf_counter()
        analysis = deterministic_grounded_analysis(payload)
        return AnalysisResult(
            analysis=analysis,
            telemetry=ModelTelemetry(
                trace_id=trace_id,
                provider="mock",
                model=self.settings.qwen_model,
                latency_ms=round((time.perf_counter() - started) * 1000),
                retry_count=0,
                success=True,
                structured_validation_success=True,
            ),
        )

    async def classify_intent(self, question: str, *, conversation_history: list[dict[str, str]], trace_id: str) -> IntentClassificationResult:
        started = time.perf_counter()
        # Deterministic stand-in for local/offline dev and tests: no keyword
        # match already means "ambiguous", so without a real model to judge
        # meaning, default to the safer of the two options only when there
        # is conversational context to plausibly be a follow-up to.
        intent = "analytical" if conversation_history else "conversational"
        return IntentClassificationResult(
            classification=IntentClassification(intent=intent),
            telemetry=ModelTelemetry(
                trace_id=trace_id, provider="mock", model=self.settings.qwen_model,
                latency_ms=round((time.perf_counter() - started) * 1000),
                retry_count=0, success=True, structured_validation_success=True,
            ),
        )

    async def health_check(self) -> ModelHealth:
        return ModelHealth(mode="mock", status="mock", provider="mock", model=self.settings.qwen_model)


class QwenOpenAICompatibleProvider:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    @property
    def endpoint(self) -> str:
        return f"{self.settings.qwen_base_url.rstrip('/')}/chat/completions"

    @staticmethod
    def _strip_reasoning(content: str) -> str:
        return re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL | re.IGNORECASE).strip()

    @classmethod
    def _parse_analysis(cls, content: str) -> StructuredAnalysis:
        clean = cls._strip_reasoning(content)
        try:
            value = json.loads(clean)
        except json.JSONDecodeError:
            fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL | re.IGNORECASE)
            embedded = fenced or re.search(r"\{.*\}", clean, flags=re.DOTALL)
            if not embedded:
                raise ValueError("No structured object found")
            value = json.loads(embedded.group(1) if fenced else embedded.group(0))
        return StructuredAnalysis.model_validate(value)

    @staticmethod
    def _messages(payload: TrustedAnalysisPayload, language: str) -> list[dict[str, str]]:
        language_instruction = {
            "id": "Write all user-facing content in Bahasa Indonesia.",
            "en": "Write all user-facing content in English.",
        }.get(language, "Use the same language as the user's question.")
        system = f"""You are a concise enterprise business analyst. {language_instruction}
Use only the trusted payload supplied by the application. Never invent unavailable causes.
Distinguish facts from inference. Do not claim inventory impact unless inventory fields exist.
Do not claim channel impact unless channel fields exist. Never reveal hidden reasoning.
Return JSON only with exactly this schema:
{{"summary":"string","drivers":[{{"title":"string","description":"string","evidence":"string"}}],"recommended_actions":["string"],"caveats":["string"]}}
Prioritize material business impact and cite evidence using supplied field names and values.
The payload may include conversation_history: prior turns in this session, oldest first. Use it
only to keep the answer coherent with what was already discussed (e.g. resolve "that region" or
avoid repeating the same explanation) — never as a source of facts; all facts must still come
from query_result and business_context."""
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": payload.model_dump_json()},
        ]

    async def generate_structured(self, payload: TrustedAnalysisPayload, *, language: str, trace_id: str) -> AnalysisResult:
        if not self.settings.qwen_base_url:
            raise LLMProviderError("unavailable")
        headers = {"Content-Type": "application/json"}
        token = self.settings.qwen_api_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = {
            "model": self.settings.qwen_model,
            "messages": self._messages(payload, language),
            "temperature": 0.1,
            "max_tokens": self.settings.qwen_max_tokens,
            "chat_template_kwargs": {
                "enable_thinking": not self.settings.qwen_disable_thinking,
                "preserve_thinking": False,
            },
        }
        started = time.perf_counter()
        last_code = "unavailable"
        last_status: int | None = None
        for attempt in range(self.settings.qwen_max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.qwen_request_timeout_seconds,
                    verify=self.settings.qwen_verify_ssl,
                    transport=self.transport,
                ) as client:
                    response = await client.post(self.endpoint, headers=headers, json=body)
                last_status = response.status_code
                if response.status_code in {401, 403}:
                    raise LLMProviderError(
                        "auth_required",
                        retry_count=attempt,
                        http_status=response.status_code,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                    )
                if response.status_code >= 400:
                    last_code = "http_error"
                    if response.status_code < 500:
                        raise LLMProviderError(
                            last_code,
                            retry_count=attempt,
                            http_status=response.status_code,
                            latency_ms=round((time.perf_counter() - started) * 1000),
                        )
                    raise ValueError("Retryable upstream status")
                raw = response.json()
                content = raw["choices"][0]["message"]["content"]
                analysis = self._parse_analysis(content)
                usage = raw.get("usage") or {}
                return AnalysisResult(
                    analysis=analysis,
                    telemetry=ModelTelemetry(
                        trace_id=trace_id,
                        provider="qwen_openai_compatible",
                        model=self.settings.qwen_model,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        retry_count=attempt,
                        success=True,
                        http_status=response.status_code,
                        structured_validation_success=True,
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                    ),
                )
            except LLMProviderError:
                raise
            except httpx.TimeoutException:
                last_code = "timeout"
            except httpx.RequestError:
                last_code = "unavailable"
            except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError, ValidationError):
                last_code = "invalid_response"
            logger.warning("Qwen analysis attempt failed code=%s status=%s attempt=%s", last_code, last_status, attempt + 1)
            if attempt >= self.settings.qwen_max_retries:
                raise LLMProviderError(
                    last_code,
                    retry_count=attempt,
                    http_status=last_status,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
        raise LLMProviderError(
            last_code,
            retry_count=self.settings.qwen_max_retries,
            http_status=last_status,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )

    async def health_check(self) -> ModelHealth:
        status = "unknown" if self.settings.qwen_base_url else "unavailable"
        return ModelHealth(mode="remote", status=status, provider="qwen_openai_compatible", model=self.settings.qwen_model)

    @staticmethod
    def _classification_messages(question: str, conversation_history: list[dict[str, str]]) -> list[dict[str, str]]:
        system = """You classify one user message for a commercial-analytics chat assistant.
Return JSON only: {"intent":"analytical"|"conversational"}
"analytical" = the message is asking about, or is a natural follow-up to (clarifying, requesting
more detail on, or reacting to) the business/commercial data already being discussed in this
session — sales, forecasts, products, regions, channels, market signals, and similar.
"conversational" = anything else: greetings, small talk, questions about the assistant itself
(its capabilities, language support, identity), or a topic change unrelated to the data being
discussed. When in doubt and there is no concrete data-related follow-up cue, prefer
"conversational" — do not guess "analytical" just because a conversation is already underway."""
        history_text = "\n".join(f"{item.get('role', '?')}: {item.get('content', '')}" for item in conversation_history[-6:])
        user = f"Recent conversation (oldest first):\n{history_text or '(none)'}\n\nMessage to classify: {question}"
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    async def classify_intent(self, question: str, *, conversation_history: list[dict[str, str]], trace_id: str) -> IntentClassificationResult:
        if not self.settings.qwen_base_url:
            raise LLMProviderError("unavailable")
        headers = {"Content-Type": "application/json"}
        token = self.settings.qwen_api_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = {
            "model": self.settings.qwen_model,
            "messages": self._classification_messages(question, conversation_history),
            "temperature": 0.0,
            "max_tokens": 50,
            "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.qwen_request_timeout_seconds,
                verify=self.settings.qwen_verify_ssl,
                transport=self.transport,
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
            if response.status_code >= 400:
                raise LLMProviderError("http_error", http_status=response.status_code, latency_ms=round((time.perf_counter() - started) * 1000))
            raw = response.json()
            content = self._strip_reasoning(raw["choices"][0]["message"]["content"])
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            value = json.loads(match.group(0) if match else content)
            classification = IntentClassification.model_validate(value)
            usage = raw.get("usage") or {}
            return IntentClassificationResult(
                classification=classification,
                telemetry=ModelTelemetry(
                    trace_id=trace_id, provider="qwen_openai_compatible", model=self.settings.qwen_model,
                    latency_ms=round((time.perf_counter() - started) * 1000), retry_count=0, success=True,
                    http_status=response.status_code, structured_validation_success=True,
                    prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        except LLMProviderError:
            raise
        except httpx.TimeoutException:
            raise LLMProviderError("timeout", latency_ms=round((time.perf_counter() - started) * 1000))
        except httpx.RequestError:
            raise LLMProviderError("unavailable", latency_ms=round((time.perf_counter() - started) * 1000))
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise LLMProviderError("invalid_response", latency_ms=round((time.perf_counter() - started) * 1000))


class LiteLLMProvider(QwenOpenAICompatibleProvider):
    """Routes analysis requests through the LiteLLM proxy (litellm/config.yaml)
    instead of calling Qwen directly. Reuses QwenOpenAICompatibleProvider's
    request/retry/parsing logic wholesale — the only difference is which
    endpoint, model name, and auth header are used, and that the response is
    inspected for whether LiteLLM silently fell back to a different model
    group than the one requested (e.g. the planned Agent Studio workflow
    being unavailable and LiteLLM routing to commercial-intelligence
    instead), so that fallback can be surfaced to the user rather than
    passed through invisibly."""

    def __init__(self, settings: Settings, *, model_group: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)
        self.requested_model_group = model_group or settings.litellm_model_group

    @property
    def endpoint(self) -> str:
        return f"{self.settings.litellm_base_url.rstrip('/')}/chat/completions"

    async def generate_structured(self, payload: TrustedAnalysisPayload, *, language: str, trace_id: str) -> AnalysisResult:
        if not self.settings.litellm_base_url:
            raise LLMProviderError("unavailable")
        headers = {"Content-Type": "application/json"}
        api_key = self.settings.litellm_api_key.get_secret_value()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": self.requested_model_group,
            "messages": self._messages(payload, language),
            "temperature": 0.1,
            "max_tokens": self.settings.qwen_max_tokens,
            "chat_template_kwargs": {
                "enable_thinking": not self.settings.qwen_disable_thinking,
                "preserve_thinking": False,
            },
        }
        started = time.perf_counter()
        last_code = "unavailable"
        last_status: int | None = None
        for attempt in range(self.settings.qwen_max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.qwen_request_timeout_seconds,
                    verify=self.settings.qwen_verify_ssl,
                    transport=self.transport,
                ) as client:
                    response = await client.post(self.endpoint, headers=headers, json=body)
                last_status = response.status_code
                if response.status_code in {401, 403}:
                    raise LLMProviderError(
                        "auth_required", retry_count=attempt, http_status=response.status_code,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                    )
                if response.status_code >= 400:
                    last_code = "http_error"
                    if response.status_code < 500:
                        raise LLMProviderError(
                            last_code, retry_count=attempt, http_status=response.status_code,
                            latency_ms=round((time.perf_counter() - started) * 1000),
                        )
                    raise ValueError("Retryable upstream status")
                raw = response.json()
                content = raw["choices"][0]["message"]["content"]
                analysis = self._parse_analysis(content)
                usage = raw.get("usage") or {}
                served_model_group = str(raw.get("model") or self.requested_model_group)
                fallback_used = (
                    self.requested_model_group == self.settings.litellm_agent_studio_model_group
                    and served_model_group != self.requested_model_group
                )
                if fallback_used:
                    fallback_notice = (
                        "The Agent Studio workflow was unavailable, so this answer was generated "
                        "by the standard commercial-intelligence model instead."
                        if language != "id"
                        else "Alur kerja Agent Studio sedang tidak tersedia, sehingga jawaban ini "
                        "dihasilkan oleh model commercial-intelligence standar."
                    )
                    if fallback_notice not in analysis.caveats:
                        analysis = analysis.model_copy(update={"caveats": [*analysis.caveats, fallback_notice][:12]})
                return AnalysisResult(
                    analysis=analysis,
                    telemetry=ModelTelemetry(
                        trace_id=trace_id, provider="litellm", model=served_model_group,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        retry_count=attempt, success=True, fallback_used=fallback_used,
                        http_status=response.status_code, structured_validation_success=True,
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                    ),
                )
            except LLMProviderError:
                raise
            except httpx.TimeoutException:
                last_code = "timeout"
            except httpx.RequestError:
                last_code = "unavailable"
            except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError, ValidationError):
                last_code = "invalid_response"
            logger.warning("LiteLLM analysis attempt failed code=%s status=%s attempt=%s model_group=%s", last_code, last_status, attempt + 1, self.requested_model_group)
            if attempt >= self.settings.qwen_max_retries:
                raise LLMProviderError(
                    last_code, retry_count=attempt, http_status=last_status,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
        raise LLMProviderError(
            last_code, retry_count=self.settings.qwen_max_retries, http_status=last_status,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )

    async def health_check(self) -> ModelHealth:
        status = "unknown" if self.settings.litellm_base_url else "unavailable"
        return ModelHealth(mode="remote", status=status, provider="litellm", model=self.requested_model_group)

    async def classify_intent(self, question: str, *, conversation_history: list[dict[str, str]], trace_id: str) -> IntentClassificationResult:
        if not self.settings.litellm_base_url:
            raise LLMProviderError("unavailable")
        headers = {"Content-Type": "application/json"}
        api_key = self.settings.litellm_api_key.get_secret_value()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": self.requested_model_group,
            "messages": self._classification_messages(question, conversation_history),
            "temperature": 0.0,
            "max_tokens": 50,
            "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.qwen_request_timeout_seconds,
                verify=self.settings.qwen_verify_ssl,
                transport=self.transport,
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
            if response.status_code >= 400:
                raise LLMProviderError("http_error", http_status=response.status_code, latency_ms=round((time.perf_counter() - started) * 1000))
            raw = response.json()
            content = self._strip_reasoning(raw["choices"][0]["message"]["content"])
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            value = json.loads(match.group(0) if match else content)
            classification = IntentClassification.model_validate(value)
            usage = raw.get("usage") or {}
            return IntentClassificationResult(
                classification=classification,
                telemetry=ModelTelemetry(
                    trace_id=trace_id, provider="litellm", model=str(raw.get("model") or self.requested_model_group),
                    latency_ms=round((time.perf_counter() - started) * 1000), retry_count=0, success=True,
                    http_status=response.status_code, structured_validation_success=True,
                    prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        except LLMProviderError:
            raise
        except httpx.TimeoutException:
            raise LLMProviderError("timeout", latency_ms=round((time.perf_counter() - started) * 1000))
        except httpx.RequestError:
            raise LLMProviderError("unavailable", latency_ms=round((time.perf_counter() - started) * 1000))
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise LLMProviderError("invalid_response", latency_ms=round((time.perf_counter() - started) * 1000))
