"""Factory for AI providers and LangChain chat models."""

from __future__ import annotations

from typing import Dict, Type

from config.settings import settings

from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .groq_provider import GroqProvider
from .openai_provider import OpenAIProvider
from .provider import AIProvider, ProviderError

_REGISTRY: Dict[str, Type[AIProvider]] = {
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "anthropic": ClaudeProvider,
}


def create_provider(
    provider_id: str,
    api_key: str,
    model: str | None = None,
) -> AIProvider:
    """Instantiate a provider adapter by id."""
    cls = _REGISTRY.get(provider_id)
    if not cls:
        raise ProviderError("invalid_provider", f"Unknown provider: {provider_id}")
    return cls(api_key=api_key, model=model)


def get_langchain_chat_model(
    provider_id: str,
    api_key: str,
    model: str,
    temperature: float | None = None,
):
    """Build a LangChain chat model for the agent pipeline."""
    temp = settings.agent_temperature if temperature is None else temperature
    provider = create_provider(provider_id, api_key, model)
    return provider.get_langchain_model(temperature=temp)
