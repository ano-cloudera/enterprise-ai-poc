from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.llm.providers import GeminiProvider, OpenAIProvider, QwenProvider


class Result(BaseModel):
    answer: str


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "provider_name"),
    [(QwenProvider, "qwen"), (OpenAIProvider, "openai")],
)
async def test_openai_compatible_providers_return_validated_structured_output(
    provider_type, provider_name
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"grounded"}'}}]},
        )

    settings = Settings(
        _env_file=None,
        qwen_base_url="https://qwen.internal/v1",
        qwen_model="qwen-model",
        qwen_api_key="qwen-secret",
        openai_base_url="https://openai.example/v1",
        openai_model="openai-model",
        openai_api_key="openai-secret",
    )
    provider = provider_type(settings, transport=httpx.MockTransport(handler))

    result = await provider.generate_structured(
        [{"role": "user", "content": "question"}], Result, temperature=0, max_tokens=123
    )

    assert result == Result(answer="grounded")
    assert captured["model"] == f"{provider_name}-model"
    if provider_name == "openai":
        assert "temperature" not in captured
        assert captured["max_completion_tokens"] == 123
        assert "max_tokens" not in captured
    else:
        assert captured["temperature"] == 0
        assert captured["max_tokens"] == 123


@pytest.mark.asyncio
async def test_gemini_provider_returns_validated_structured_output() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.headers["x-goog-api-key"] == "gemini-secret"
        assert "key=" not in str(request.url)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"answer":"grounded"}'}]}}]},
        )

    settings = Settings(
        _env_file=None,
        gemini_base_url="https://gemini.example/v1beta",
        gemini_model="gemini-model",
        gemini_api_key="gemini-secret",
    )
    provider = GeminiProvider(settings, transport=httpx.MockTransport(handler))

    result = await provider.generate_structured(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "question"},
        ],
        Result,
        temperature=0.2,
        max_tokens=321,
    )

    assert result == Result(answer="grounded")
    assert captured["generationConfig"]["temperature"] == 0.2
    assert captured["generationConfig"]["maxOutputTokens"] == 321
    assert captured["systemInstruction"]["parts"] == [{"text": "system"}]
