from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm.providers import LiteLLMProvider, LLMProvider, MockLLMProvider, QwenOpenAICompatibleProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Picks the analysis provider for llm_mode=remote: routes through the
    LiteLLM proxy when one is configured (LITELLM_BASE_URL set), otherwise
    falls back to calling Qwen directly — so existing deployments that
    haven't stood up the LiteLLM Application keep working unchanged."""
    configured = settings or get_settings()
    if configured.llm_mode == "mock":
        return MockLLMProvider(configured)
    if configured.litellm_base_url:
        model_group = configured.litellm_agent_studio_model_group if configured.litellm_use_agent_studio else configured.litellm_model_group
        return LiteLLMProvider(configured, model_group=model_group)
    return QwenOpenAICompatibleProvider(configured)
