"""Groq provider adapter."""

from __future__ import annotations

from typing import List

from config.settings import settings
from utils.logging_config import get_logger
from utils.security import sanitize_error

from .provider import AIProvider, ValidationResult

logger = get_logger(__name__)


class GroqProvider(AIProvider):
    provider_id = "groq"
    label = "Groq"

    def list_models(self) -> List[str]:
        return list(settings.providers["groq"].models)

    def validate(self, timeout: float = 20.0) -> ValidationResult:
        if not self.api_key:
            return ValidationResult(False, "API key is required.", "invalid_key")
        try:
            from groq import Groq

            client = Groq(api_key=self.api_key, timeout=timeout)
            models_page = client.models.list()
            discovered = [m.id for m in models_page.data]
            catalog = self.list_models()
            available = [m for m in catalog if m in discovered] or catalog
            return ValidationResult(
                ok=True,
                message="Connected to Groq",
                models=available,
            )
        except Exception as exc:  # noqa: BLE001
            err = self.classify_exception(exc)
            logger.warning("Groq validation failed: %s", sanitize_error(exc))
            return ValidationResult(False, err.message, err.code)

    def get_langchain_model(self, temperature: float = 0.0):
        from langchain_groq import ChatGroq

        model = self.model or settings.providers["groq"].default_model
        return ChatGroq(
            model=model,
            api_key=self.api_key,
            temperature=temperature,
        )
