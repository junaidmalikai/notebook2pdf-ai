"""Google Gemini provider adapter."""

from __future__ import annotations

from typing import List

from config.settings import settings
from utils.logging_config import get_logger
from utils.security import sanitize_error

from .provider import AIProvider, ValidationResult

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    provider_id = "gemini"
    label = "Google Gemini"

    def list_models(self) -> List[str]:
        return list(settings.providers["gemini"].models)

    def validate(self, timeout: float = 20.0) -> ValidationResult:
        if not self.api_key:
            return ValidationResult(False, "API key is required.", "invalid_key")
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            # Lightweight request — list models
            models = list(client.models.list())
            discovered = []
            for m in models:
                name = getattr(m, "name", "") or ""
                # names look like "models/gemini-2.0-flash"
                short = name.split("/")[-1] if name else ""
                if short:
                    discovered.append(short)
            catalog = self.list_models()
            available = [m for m in catalog if m in discovered] or catalog
            return ValidationResult(
                ok=True,
                message="Connected to Google Gemini",
                models=available,
            )
        except Exception as exc:  # noqa: BLE001
            # Fallback: try older google-generativeai package
            try:
                import google.generativeai as genai_old

                genai_old.configure(api_key=self.api_key)
                models = list(genai_old.list_models())
                discovered = [
                    m.name.replace("models/", "")
                    for m in models
                    if hasattr(m, "name")
                ]
                catalog = self.list_models()
                available = [m for m in catalog if m in discovered] or catalog
                return ValidationResult(
                    ok=True,
                    message="Connected to Google Gemini",
                    models=available,
                )
            except Exception as exc2:  # noqa: BLE001
                err = self.classify_exception(exc2 if exc2 else exc)
                logger.warning("Gemini validation failed: %s", sanitize_error(exc2 or exc))
                return ValidationResult(False, err.message, err.code)

    def get_langchain_model(self, temperature: float = 0.0):
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = self.model or settings.providers["gemini"].default_model
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.api_key,
            temperature=temperature,
        )
