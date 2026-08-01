"""Shared LLM helpers for agent decisions."""

from __future__ import annotations

from services.ai.factory import get_langchain_chat_model


def get_llm(
    provider_id: str,
    api_key: str,
    model: str,
    *,
    temperature: float = 0.0,
):
    return get_langchain_chat_model(
        provider_id,
        api_key,
        model,
        temperature=temperature,
    )
