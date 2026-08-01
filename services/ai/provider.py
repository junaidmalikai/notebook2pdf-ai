"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ProviderError(Exception):
    """Raised when a provider operation fails with a user-facing message."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ErrorCode(str, Enum):
    INVALID_KEY = "invalid_key"
    AUTH_FAILED = "auth_failed"
    QUOTA = "quota_exceeded"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    TIMEOUT = "timeout"
    MODEL = "model_unavailable"
    PROVIDER = "provider_unavailable"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Outcome of an API-key validation attempt."""

    ok: bool
    message: str
    code: Optional[str] = None
    models: List[str] = field(default_factory=list)
    via_env: bool = False


class AIProvider(ABC):
    """Common interface implemented by every LLM vendor adapter."""

    provider_id: str
    label: str

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = (api_key or "").strip()
        self.model = model

    @abstractmethod
    def validate(self, timeout: float = 20.0) -> ValidationResult:
        """Perform a lightweight authenticated request to verify credentials."""

    @abstractmethod
    def list_models(self) -> List[str]:
        """Return supported / discovered model identifiers."""

    @abstractmethod
    def get_langchain_model(self, temperature: float = 0.0):
        """Return a LangChain chat model bound to this provider."""

    def classify_exception(self, exc: Exception) -> ProviderError:
        """Map vendor exceptions to stable, user-friendly errors."""
        text = str(exc).lower()
        name = type(exc).__name__.lower()

        if "timeout" in text or "timed out" in text:
            return ProviderError(ErrorCode.TIMEOUT, "Network timeout — please try again.")
        if any(k in text for k in ("connection", "network", "unreachable", "dns")):
            return ProviderError(ErrorCode.NETWORK, "Network unavailable — check your internet connection.")
        if any(k in text for k in ("rate limit", "rate_limit", "429", "too many requests")):
            return ProviderError(ErrorCode.RATE_LIMIT, "API rate limit exceeded — wait and retry.")
        if any(k in text for k in ("quota", "billing", "insufficient", "exceeded your current quota")):
            return ProviderError(ErrorCode.QUOTA, "API quota exceeded — check your provider billing.")
        if any(
            k in text
            for k in (
                "invalid api key",
                "incorrect api key",
                "authentication",
                "unauthorized",
                "401",
                "403",
                "permission",
                "invalid_api_key",
                "api key not valid",
            )
        ) or "auth" in name:
            return ProviderError(ErrorCode.INVALID_KEY, "Invalid API Key — authentication failed.")
        if "model" in text and any(k in text for k in ("not found", "does not exist", "unavailable")):
            return ProviderError(ErrorCode.MODEL, "Selected model is unavailable.")
        return ProviderError(ErrorCode.UNKNOWN, f"Provider error: {exc}")
