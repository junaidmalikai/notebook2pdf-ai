"""AI Provider sidebar with automatic API key validation (no buttons)."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

import streamlit as st

from config.settings import settings
from services.ai.factory import create_provider
from utils.logging_config import get_logger
from utils.security import mask_api_key, sanitize_error

logger = get_logger(__name__)

_PROVIDER_LABELS = {pid: cfg.label for pid, cfg in settings.providers.items()}

# Avoid validating on every keystroke — wait for a paste/complete-looking key.
_KEY_READY = re.compile(
    r"^(sk-ant-|sk-|gsk_|AIza)[A-Za-z0-9_\-]{16,}$|^[A-Za-z0-9_\-]{32,}$"
)


def _init_ai_state() -> None:
    defaults: Dict[str, Any] = {
        "ai_provider": "openai",
        "ai_api_key": "",
        "ai_model": settings.providers["openai"].default_model,
        "ai_connected": False,
        "ai_via_env": False,
        "ai_status_msg": "",
        "ai_available_models": list(settings.providers["openai"].models),
        "ai_context_window": None,
        "ai_last_validated_fingerprint": "",
        "ai_validating": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _fingerprint(provider: str, key: str) -> str:
    return f"{provider}::{key.strip()}"


def _apply_success(pid: str, key: str, model: str, models: list, via_env: bool, msg: str) -> None:
    cfg = settings.providers[pid]
    st.session_state.ai_provider = pid
    st.session_state.ai_api_key = key
    st.session_state.ai_connected = True
    st.session_state.ai_via_env = via_env
    st.session_state.ai_status_msg = msg
    st.session_state.ai_available_models = models or list(cfg.models)
    if model not in st.session_state.ai_available_models:
        model = cfg.default_model
        if model not in st.session_state.ai_available_models and st.session_state.ai_available_models:
            model = st.session_state.ai_available_models[0]
    st.session_state.ai_model = model
    st.session_state.ai_context_window = cfg.context_windows.get(model)
    st.session_state.ai_last_validated_fingerprint = _fingerprint(pid, key)


def _apply_failure(msg: str) -> None:
    st.session_state.ai_connected = False
    st.session_state.ai_via_env = False
    st.session_state.ai_api_key = ""
    st.session_state.ai_status_msg = msg
    st.session_state.ai_context_window = None


def _auto_validate(pid: str, key: str) -> None:
    """Validate key automatically when it looks complete; skip unchanged fingerprints."""
    key = (key or "").strip()
    if not key:
        _apply_failure("")
        st.session_state.ai_last_validated_fingerprint = ""
        return

    if not _KEY_READY.match(key):
        st.session_state.ai_connected = False
        st.session_state.ai_status_msg = ""
        return

    fp = _fingerprint(pid, key)
    if (
        fp == st.session_state.ai_last_validated_fingerprint
        and st.session_state.ai_connected
    ):
        return
    # Also skip re-calling API for the same invalid key
    if (
        fp == st.session_state.ai_last_validated_fingerprint
        and not st.session_state.ai_connected
        and st.session_state.ai_status_msg
    ):
        return

    cfg = settings.providers[pid]
    model = st.session_state.ai_model
    if model not in cfg.models:
        model = cfg.default_model

    st.session_state.ai_validating = True
    try:
        provider = create_provider(pid, key, model)
        result = provider.validate(timeout=settings.validation_timeout)
        if result.ok:
            _apply_success(
                pid,
                key,
                model,
                result.models or list(cfg.models),
                via_env=False,
                msg="Connected",
            )
            logger.info("Auto-validated provider=%s", pid)
        else:
            _apply_failure(result.message or "Invalid API Key")
            st.session_state.ai_last_validated_fingerprint = fp
    except Exception as exc:  # noqa: BLE001
        _apply_failure(sanitize_error(exc))
        st.session_state.ai_last_validated_fingerprint = fp
    finally:
        st.session_state.ai_validating = False


def _try_env_autoconnect() -> None:
    if st.session_state.ai_connected:
        return
    # If user already typed a key into the widget, prefer that path
    typed = (st.session_state.get("ai_api_key_input") or "").strip()
    if typed:
        return

    order = [st.session_state.ai_provider] + [
        p for p in settings.providers if p != st.session_state.ai_provider
    ]
    for pid in order:
        key = settings.env_api_key(pid)
        if not key:
            continue
        cfg = settings.providers[pid]
        model = cfg.default_model
        try:
            provider = create_provider(pid, key, model)
            result = provider.validate(timeout=settings.validation_timeout)
            if result.ok:
                _apply_success(
                    pid,
                    key,
                    model,
                    result.models or list(cfg.models),
                    via_env=True,
                    msg="Connected via Environment Variables",
                )
                st.session_state.ai_api_key_input = ""
                return
        except Exception as exc:  # noqa: BLE001
            logger.debug("Env autoconnect skipped for %s: %s", pid, sanitize_error(exc))


def is_ai_ready() -> bool:
    _init_ai_state()
    return bool(st.session_state.ai_connected and st.session_state.ai_api_key)


def get_connection() -> Optional[Dict[str, Any]]:
    if not is_ai_ready():
        return None
    return {
        "provider_id": st.session_state.ai_provider,
        "api_key": st.session_state.ai_api_key,
        "model": st.session_state.ai_model,
        "via_env": st.session_state.ai_via_env,
        "label": _PROVIDER_LABELS.get(st.session_state.ai_provider, "AI"),
    }


def render_ai_sidebar() -> bool:
    """Render AI sidebar. Auto-validates on key paste / provider change."""
    _init_ai_state()
    _try_env_autoconnect()

    with st.sidebar:
        st.markdown("### Notebook2PDF AI")
        st.caption("Choose a provider and paste your API key — validation is automatic.")

        provider_ids = list(settings.providers.keys())
        labels = [_PROVIDER_LABELS[p] for p in provider_ids]
        current = st.session_state.ai_provider
        try:
            idx = provider_ids.index(current)
        except ValueError:
            idx = 0

        selected_label = st.selectbox("Provider", options=labels, index=idx)
        new_pid = provider_ids[labels.index(selected_label)]
        provider_changed = new_pid != st.session_state.ai_provider
        if provider_changed:
            st.session_state.ai_provider = new_pid
            st.session_state.ai_connected = False
            st.session_state.ai_via_env = False
            st.session_state.ai_status_msg = ""
            st.session_state.ai_last_validated_fingerprint = ""
            st.session_state.ai_model = settings.providers[new_pid].default_model
            st.session_state.ai_available_models = list(
                settings.providers[new_pid].models
            )

        cfg = settings.providers[st.session_state.ai_provider]
        env_hint = settings.env_api_key(st.session_state.ai_provider)
        placeholder = (
            f"Using {mask_api_key(env_hint)} from env" if env_hint else "Paste API key..."
        )

        api_key = st.text_input(
            "API Key",
            type="password",
            key="ai_api_key_input",
            placeholder=placeholder,
            help="Validated automatically. Stored only in session state.",
        )

        # Auto-validate whenever the typed key (or provider) changes
        typed = (api_key or "").strip()
        if typed:
            _auto_validate(st.session_state.ai_provider, typed)
        elif provider_changed and env_hint:
            _auto_validate(st.session_state.ai_provider, env_hint)
        elif not typed and not st.session_state.ai_via_env:
            if st.session_state.ai_connected and not env_hint:
                _apply_failure("")

        if st.session_state.ai_validating:
            st.info("Validating API key...")
        elif st.session_state.ai_connected:
            via = " via Environment Variables" if st.session_state.ai_via_env else ""
            st.markdown(
                f'<div class="ai-status ai-ok">Connected{via}<br/>'
                f'{_PROVIDER_LABELS[st.session_state.ai_provider]} | '
                f'{st.session_state.ai_model}</div>',
                unsafe_allow_html=True,
            )
        elif st.session_state.ai_status_msg:
            st.markdown(
                f'<div class="ai-status ai-bad">{st.session_state.ai_status_msg}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="ai-status ai-idle">Waiting for API key</div>',
                unsafe_allow_html=True,
            )

        models = st.session_state.ai_available_models or list(cfg.models)
        if st.session_state.ai_model not in models:
            st.session_state.ai_model = models[0] if models else cfg.default_model

        model = st.selectbox(
            "Model",
            options=models,
            index=models.index(st.session_state.ai_model)
            if st.session_state.ai_model in models
            else 0,
            disabled=not st.session_state.ai_connected,
        )
        if model != st.session_state.ai_model:
            st.session_state.ai_model = model
            st.session_state.ai_context_window = cfg.context_windows.get(model)

        ctx = st.session_state.ai_context_window or cfg.context_windows.get(
            st.session_state.ai_model
        )
        if ctx and st.session_state.ai_connected:
            st.caption(f"Context window | ~{ctx:,} tokens")

        st.markdown("---")
        if st.session_state.ai_connected:
            st.success("Application unlocked")
        else:
            st.warning("Please enter a valid API key to continue.")

    return is_ai_ready()
