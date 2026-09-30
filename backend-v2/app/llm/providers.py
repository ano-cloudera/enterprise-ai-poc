from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.llm.base import ProviderError, StructuredT


def _structured_json(text: str) -> Any:
    value = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1)
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ProviderError("INVALID_STRUCTURED_OUTPUT") from exc


class _OpenAICompatibleProvider:
    provider_name = "openai"

    def __init__(
        self,
        settings: Settings,
        *,
        base_url: str,
        api_key: str,
        model: str,
        verify_ssl: bool,
        modern_openai_parameters: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.verify_ssl = verify_ssl
        self.modern_openai_parameters = modern_openai_parameters
        self.transport = transport

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[StructuredT],
        *,
        temperature: float,
        max_tokens: int,
    ) -> StructuredT:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
        schema_instruction = (
            "Return exactly one JSON object that validates against this JSON Schema. "
            f"Do not rename fields or add fields outside the schema: {schema}"
        )
        request_messages = [dict(message) for message in messages]
        if request_messages and request_messages[0].get("role") == "system":
            request_messages[0]["content"] += "\n\n" + schema_instruction
        else:
            request_messages.insert(0, {"role": "system", "content": schema_instruction})
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for attempt in range(2):
            body = {
                "model": self.model,
                "messages": request_messages,
                "response_format": {"type": "json_object"},
            }
            if self.modern_openai_parameters:
                body["max_completion_tokens"] = max_tokens
            else:
                body["temperature"] = temperature
                body["max_tokens"] = max_tokens
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.llm_request_timeout_seconds,
                    verify=self.verify_ssl,
                    transport=self.transport,
                ) as client:
                    response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                    response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            except httpx.TimeoutException as exc:
                raise ProviderError("TIMEOUT") from exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderError("PROVIDER_ERROR") from exc
            try:
                return response_model.model_validate(_structured_json(content))
            except (ProviderError, ValidationError) as exc:
                if attempt == 1:
                    raise ProviderError("INVALID_STRUCTURED_OUTPUT") from exc
                request_messages = [
                    *request_messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "The previous JSON did not validate. Return only a corrected JSON object matching the exact schema above.",
                    },
                ]
        raise ProviderError("INVALID_STRUCTURED_OUTPUT")


class QwenProvider(_OpenAICompatibleProvider):
    provider_name = "qwen"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(
            settings,
            base_url=settings.qwen_base_url,
            api_key=settings.qwen_api_key.get_secret_value(),
            model=settings.qwen_model,
            verify_ssl=settings.qwen_verify_ssl,
            transport=transport,
        )


class OpenAIProvider(_OpenAICompatibleProvider):
    provider_name = "openai"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(
            settings,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            verify_ssl=settings.openai_verify_ssl,
            modern_openai_parameters=True,
            transport=transport,
        )


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[StructuredT],
        *,
        temperature: float,
        max_tokens: int,
    ) -> StructuredT:
        system_parts = [{"text": item["content"]} for item in messages if item["role"] == "system"]
        contents = [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in messages
            if item["role"] != "system"
        ]
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": response_model.model_json_schema(),
            },
        }
        if system_parts:
            body["systemInstruction"] = {"parts": system_parts}
        url = f"{self.settings.gemini_base_url.rstrip('/')}/models/{self.settings.gemini_model}:generateContent"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.llm_request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": self.settings.gemini_api_key.get_secret_value()},
                    json=body,
                )
                response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return response_model.model_validate(_structured_json(text))
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("TIMEOUT") from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("PROVIDER_ERROR") from exc
