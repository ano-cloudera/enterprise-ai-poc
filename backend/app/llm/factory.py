from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm.providers import LLMProvider, MockLLMProvider, QwenOpenAICompatibleProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    configured = settings or get_settings()
    if configured.llm_mode == "mock":
        return MockLLMProvider(configured)
    return QwenOpenAICompatibleProvider(configured)
