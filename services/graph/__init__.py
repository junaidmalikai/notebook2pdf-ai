"""LangGraph conversion workflow package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workflow import (
        build_conversion_graph,
        export_graph_mermaid,
        get_checkpointed_graph,
        get_compiled_graph,
        run_conversion_graph,
        stream_conversion_graph,
    )

__all__ = [
    "build_conversion_graph",
    "export_graph_mermaid",
    "get_checkpointed_graph",
    "get_compiled_graph",
    "run_conversion_graph",
    "stream_conversion_graph",
]


def __getattr__(name: str):
    if name in __all__:
        from . import workflow as _workflow

        return getattr(_workflow, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
