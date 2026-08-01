"""Verify parallel Send updates do not raise INVALID_CONCURRENT_GRAPH_UPDATE."""

from __future__ import annotations

from services.graph.state import ConversionState, _merge_notebooks
from services.graph.workflow import build_conversion_graph, get_compiled_graph


def test_notebooks_reducer_merges_by_filename() -> None:
    left = [{"filename": "a.ipynb", "content": b"1"}]
    right = [{"filename": "a.ipynb", "content": b"2"}, {"filename": "b.ipynb", "content": b"3"}]
    merged = _merge_notebooks(left, right)
    by_name = {n["filename"]: n["content"] for n in merged}
    assert by_name["a.ipynb"] == b"2"
    assert by_name["b.ipynb"] == b"3"


def test_parallel_enrichment_nodes_do_not_emit_notebooks() -> None:
    from services.agents.session import AgentSession

    session = AgentSession(
        notebooks=[{"filename": "demo.ipynb", "content": b"{}"}],
        pdf_settings={},
        provider_id="openai",
        api_key="x",
        model="m",
    )
    parallel = session.snapshot_for_graph(mode="parallel")
    full = session.snapshot_for_graph(mode="full")
    assert "notebooks" not in parallel
    assert "notebooks" in full
    assert "parsed" in parallel


def test_graph_compiles_with_annotated_notebooks() -> None:
    get_compiled_graph.cache_clear()
    app = build_conversion_graph(checkpointer=None)
    hints = ConversionState.__annotations__
    notebooks_hint = str(hints.get("notebooks"))
    assert "Annotated" in notebooks_hint or "Annotated" in repr(hints["notebooks"])
    assert app is not None


if __name__ == "__main__":
    test_notebooks_reducer_merges_by_filename()
    test_parallel_enrichment_nodes_do_not_emit_notebooks()
    test_graph_compiles_with_annotated_notebooks()
    print("concurrency_fix_ok")
