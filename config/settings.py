"""Central configuration for Jupyter2PDF."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Branding:
    """Company branding used across PDF, HTML, and README outputs."""

    company: str = "AL-Junaid Tech"
    author: str = "Junaid Malik"
    product: str = "Notebook → PDF"
    version: str = "1.0.0"
    copyright: str = "© 2026 AL-Junaid Tech. All rights reserved."
    website: str = "https://github.com/your-username/jupyter2pdf"
    primary: str = "#1a3a5c"
    accent: str = "#c0a060"
    secondary: str = "#2e6da4"
    watermark: str = "AL-Junaid"


@dataclass(frozen=True)
class ProviderConfig:
    """Static catalog of supported AI providers and models."""

    id: str
    label: str
    env_keys: tuple[str, ...]
    models: tuple[str, ...]
    default_model: str
    context_windows: Dict[str, int] = field(default_factory=dict)


PROVIDERS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        id="openai",
        label="OpenAI",
        env_keys=("OPENAI_API_KEY",),
        models=(
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o3",
            "o4-mini",
        ),
        default_model="gpt-4.1-mini",
        context_windows={
            "gpt-4.1": 1_047_576,
            "gpt-4.1-mini": 1_047_576,
            "gpt-4o": 128_000,
            "gpt-4o-mini": 128_000,
            "o3": 200_000,
            "o4-mini": 200_000,
        },
    ),
    "groq": ProviderConfig(
        id="groq",
        label="Groq",
        env_keys=("GROQ_API_KEY",),
        models=(
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "deepseek-r1-distill-llama-70b",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ),
        default_model="llama-3.3-70b-versatile",
        context_windows={
            "llama-3.3-70b-versatile": 128_000,
            "llama-3.1-8b-instant": 128_000,
            "deepseek-r1-distill-llama-70b": 128_000,
            "gemma2-9b-it": 8_192,
            "mixtral-8x7b-32768": 32_768,
        },
    ),
    "gemini": ProviderConfig(
        id="gemini",
        label="Google Gemini",
        env_keys=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        models=(
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
        ),
        default_model="gemini-2.5-flash",
        context_windows={
            "gemini-2.5-pro": 1_000_000,
            "gemini-2.5-flash": 1_000_000,
            "gemini-2.0-flash": 1_000_000,
            "gemini-1.5-pro": 2_000_000,
        },
    ),
    "anthropic": ProviderConfig(
        id="anthropic",
        label="Anthropic Claude",
        env_keys=("ANTHROPIC_API_KEY",),
        models=(
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
        ),
        default_model="claude-sonnet-4-20250514",
        context_windows={
            "claude-opus-4-20250514": 200_000,
            "claude-sonnet-4-20250514": 200_000,
            "claude-3-7-sonnet-20250219": 200_000,
            "claude-3-5-sonnet-20241022": 200_000,
        },
    ),
}


@dataclass
class Settings:
    """Runtime settings loaded from environment."""

    branding: Branding = field(default_factory=Branding)
    providers: Dict[str, ProviderConfig] = field(default_factory=lambda: dict(PROVIDERS))
    max_upload_mb: int = 50
    agent_temperature: float = 0.0
    validation_timeout: float = 20.0
    # Per-cell notebook execution timeout (nbclient); wall clock is higher
    execution_timeout: int = field(
        default_factory=lambda: int(os.getenv("J2P_EXECUTION_TIMEOUT", "60"))
    )
    auto_execute_notebooks: bool = field(
        default_factory=lambda: os.getenv("J2P_AUTO_EXECUTE", "1").strip()
        not in {"0", "false", "False", "no"}
    )
    quality_threshold: int = field(
        default_factory=lambda: int(os.getenv("J2P_QUALITY_THRESHOLD", "72"))
    )
    max_repair_loops: int = field(
        default_factory=lambda: int(os.getenv("J2P_MAX_REPAIR_LOOPS", "2"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("J2P_LOG_LEVEL", "INFO"))

    def env_api_key(self, provider_id: str) -> str | None:
        cfg = self.providers.get(provider_id)
        if not cfg:
            return None
        for key in cfg.env_keys:
            value = os.getenv(key, "").strip()
            if value:
                return value
        return None


settings = Settings()
