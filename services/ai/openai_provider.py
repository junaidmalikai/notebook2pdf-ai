"""OpenAI provider adapter."""

from __future__ import annotations

from typing import List

from config.settings import settings
from utils.logging_config import get_logger
from utils.security import sanitize_error

from .provider import AIProvider, ValidationResult

logger = get_logger(__name__)


class OpenAIProvider(AIProvider):
    provider_id = "openai"
    label = "OpenAI"

    def list_models(self) -> List[str]:
        return list(settings.providers["openai"].models)

    def validate(self, timeout: float = 20.0) -> ValidationResult:
        if not self.api_key:
            return ValidationResult(False, "API key is required.", "invalid_key")
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, timeout=timeout)
            # Lightweight auth check — list models
            models_page = client.models.list()
            discovered = [m.id for m in models_page.data]
            catalog = self.list_models()
            available = [m for m in catalog if m in discovered] or catalog
            return ValidationResult(
                ok=True,
                message="Connected to OpenAI",
                models=available,
            )
        except Exception as exc:  # noqa: BLE001
            err = self.classify_exception(exc)
            logger.warning("OpenAI validation failed: %s", sanitize_error(exc))
            return ValidationResult(False, err.message, err.code)

    def get_langchain_model(self, temperature: float = 0.0):
        from langchain_openai import ChatOpenAI

        model = self.model or settings.providers["openai"].default_model
        return ChatOpenAI(
            model=model,
            api_key=self.api_key,
            temperature=temperature,
        )
