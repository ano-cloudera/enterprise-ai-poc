from __future__ import annotations

import json
import logging
import re
import time
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.models import AnalysisResult, ModelHealth, ModelTelemetry, StructuredAnalysis, TrustedAnalysisPayload
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
