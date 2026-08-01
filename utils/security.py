"""Security helpers — never leak secrets into logs or UI."""

from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}", re.I),
    re.compile(r"gsk_[A-Za-z0-9_\-]{10,}", re.I),
    re.compile(r"AIza[A-Za-z0-9_\-]{10,}", re.I),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}", re.I),
    re.compile(r"(api[_-]?key|token|authorization)\s*[:=]\s*['\"]?[\w\-]+", re.I),
)


def mask_api_key(key: str | None, visible: int = 4) -> str:
    """Mask an API key for display (e.g. sk-…xxxx)."""
    if not key:
        return ""
    key = key.strip()
    if len(key) <= visible * 2:
        return "*" * len(key)
    return f"{key[:visible]}{'*' * min(12, len(key) - visible * 2)}{key[-visible:]}"


def sanitize_error(message: str | Exception) -> str:
    """Strip credential-looking substrings from error text."""
    text = str(message)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
