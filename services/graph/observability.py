"""Observability: LangSmith tracing hooks and graph diagram helpers."""

from __future__ import annotations

import os
from typing import Any

from utils.logging_config import get_logger

logger = get_logger(__name__)


def configure_langsmith() -> bool:
    """
    Enable LangSmith tracing when credentials are present.

    Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in the environment.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        return False
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "jupyter2pdf"))
    if "LANGCHAIN_API_KEY" not in os.environ and api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key
    logger.info("LangSmith tracing enabled | project=%s", os.environ.get("LANGCHAIN_PROJECT"))
    return True


def graph_mermaid(compiled_graph: Any) -> str:
    """Best-effort Mermaid diagram of a compiled LangGraph app."""
    try:
        return compiled_graph.get_graph().draw_mermaid()
    except Exception:  # noqa: BLE001
        return "graph TD\n  A[supervisor] --> B[workers]"
