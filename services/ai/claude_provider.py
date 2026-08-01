"""Anthropic Claude provider adapter."""

from __future__ import annotations

from typing import List

from config.settings import settings
from utils.logging_config import get_logger
from utils.security import sanitize_error

from .provider import AIProvider, ValidationResult

logger = get_logger(__name__)


class ClaudeProvider(AIProvider):
    provider_id = "anthropic"
    label = "Anthropic Claude"

    def list_models(self) -> List[str]:
        return list(settings.providers["anthropic"].models)

    def validate(self, timeout: float = 20.0) -> ValidationResult:
        if not self.api_key:
            return ValidationResult(False, "API key is required.", "invalid_key")
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key, timeout=timeout)
            # Lightweight authenticated probe — tiny messages call
            model = self.model or settings.providers["anthropic"].default_model
            client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return ValidationResult(
                ok=True,
                message="Connected to Anthropic Claude",
                models=self.list_models(),
            )
        except Exception as exc:  # noqa: BLE001
            err = self.classify_exception(exc)
            logger.warning("Claude validation failed: %s", sanitize_error(exc))
            return ValidationResult(False, err.message, err.code)

    def get_langchain_model(self, temperature: float = 0.0):
        from langchain_anthropic import ChatAnthropic

        model = self.model or settings.providers["anthropic"].default_model
        return ChatAnthropic(
            model=model,
            api_key=self.api_key,
            temperature=temperature,
        )
