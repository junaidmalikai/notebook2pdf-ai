"""Smoke test for LangGraph conversion + PDFSettings pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.pdf_settings import PDFSettings
from services.graph.workflow import run_conversion_graph
from services.notebook.parser import parse_notebook
from services.pdf.engine import generate_pdf


def main() -> None:
    samples = ROOT / "samples"
    samples.mkdir(exist_ok=True)

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Sample Analysis Notebook\n",
                    "\n",
                    "A short demo notebook for Jupyter2PDF.\n",
                    "\n",
                    "## Features\n",
                    "\n",
                    "- Fast conversion\n",
                    "- Beautiful PDFs\n",
                    "\n",
                    "> **NOTE:** Info callout.\n",
                    "\n",
                    "| Col A | Col B |\n",
                    "|-------|-------|\n",
                    "| 1 | 2 |\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": ["hello from notebook\n"],
                    }
                ],
                "source": [
                    "def greet(name: str) -> str:\n",
                    "    return f'Hello, {name}!'\n",
                    "\n",
                    "print(greet('World'))\n",
                ],
            },
        ],
    }
    ipynb = samples / "demo.ipynb"
    ipynb.write_text(json.dumps(nb), encoding="utf-8")
    raw = ipynb.read_bytes()

    settings = PDFSettings(
        title="Sample Analysis Notebook",
        description="Smoke-test documentation",
        author="Test Author",
        company="Test Co",
        version="1.0.0",
        language="Python",
        copyright="(c) 2026 Test",
        header_text="Internal Docs",
        footer_text="Confidential",
        watermark="",  # disabled
    )

    doc = parse_notebook(raw, "demo.ipynb")
    pdf, _ = generate_pdf(doc, settings=settings)
    (samples / "demo.pdf").write_bytes(pdf)
    print("direct pdf_kb:", len(pdf) // 1024)

    from services.notebook.analyzer import analyze_notebook
    from services.graph.workflow import build_conversion_graph
    from services.langchain_tools import list_tools

    analysis = analyze_notebook(raw, "demo.ipynb")
    assert analysis.already_executed, "demo notebook should skip execution"
    print("analyze:", analysis.summary)

    graph = build_conversion_graph()
    print("graph_nodes:", sorted(graph.get_graph().nodes))
    print("tools:", list_tools())

    print("PDFSettings + engine OK")

    # Multi-artifact ZIP via deterministic packaging_tool (no LLM)
    from services.agents.bound_tools import build_session_tools
    from services.agents.session import AgentSession

    session = AgentSession(
        notebooks=[],
        pdf_settings=settings.model_dump(),
        provider_id="openai",
        api_key="test",
        model="gpt-4o-mini",
    )
    session.pdf_artifacts = [
        {"filename": "a.pdf", "content": pdf, "title": "A"},
        {"filename": "b.pdf", "content": pdf, "title": "B"},
    ]
    tools_by_role = build_session_tools(session)
    packaging_tools = {t.name: t for t in tools_by_role["packaging"]}
    result = json.loads(packaging_tools["packaging_tool"].invoke({"reason": "smoke"}))
    assert result.get("ok"), result
    assert session.download_mime == "application/zip"
    (samples / "demo.zip").write_bytes(session.download_bytes or b"")
    print("zip_kb:", len(session.download_bytes or b"") // 1024)
    print("OK")


if __name__ == "__main__":
    main()
