"""Smoke test for AI-native LangGraph supervisor."""

from __future__ import annotations

import json

from services.graph.workflow import export_graph_mermaid, get_compiled_graph, run_conversion_graph
from services.langchain_tools import list_tools


def main() -> None:
    g = get_compiled_graph()
    print("graph", type(g).__name__)
    tools = sorted(list_tools())
    print("tools_count", len(tools))
    print("tools", tools)
    mermaid = export_graph_mermaid()
    print("has_supervisor", "supervisor" in mermaid)
    print("has_planner", "planner" in mermaid)
    print("has_quality", "quality_review" in mermaid)

    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Demo\n", "A tiny notebook.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [
                    {
                        "name": "stdout",
                        "output_type": "stream",
                        "text": ["hello\n"],
                    }
                ],
                "source": ["print('hello')\n"],
            },
        ],
        "metadata": {"kernelspec": {"language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    final = run_conversion_graph(
        notebooks=[
            {
                "filename": "demo.ipynb",
                "content": json.dumps(nb).encode("utf-8"),
            }
        ],
        pdf_settings={"title": "Demo", "description": "Smoke test"},
        provider_id="openai",
        api_key="",
        model="gpt-4o-mini",
    )
    print("empty_key_status", final.get("status"))
    print("empty_key_error", final.get("error"))
    print("logs_tail", (final.get("logs") or [])[-3:])


if __name__ == "__main__":
    main()
