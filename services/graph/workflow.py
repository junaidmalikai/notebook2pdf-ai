"""AI-native LangGraph supervisor - the ONLY conversion execution engine.

Flow:
  Streamlit -> Supervisor Graph -> Planner -> Worker Agents (tool calling)
  -> Quality Review / Repair -> PDF Assembly -> Packaging -> Download

Parallel enrichment uses LangGraph Send (native graph parallelism).
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Iterator, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from config.settings import settings
from services.agents.worker_nodes import (
    code_understanding_agent,
    coordinator_agent,
    documentation_agent,
    enrichment_merge_node,
    error_node,
    finish_node,
    image_processing_agent,
    markdown_agent,
    metadata_agent,
    notebook_analysis_agent,
    notebook_execution_agent,
    packaging_agent,
    pdf_assembly_agent,
    planner_node,
    quality_review_agent,
    route_supervisor,
    supervisor_node,
    validation_agent,
    validation_bootstrap_node,
)
from services.graph.observability import configure_langsmith, graph_mermaid
from services.graph.state import ConversionState, NotebookInput
from services.memory import get_checkpointer, remember_conversation
from utils.logging_config import get_logger

logger = get_logger(__name__)
configure_langsmith()


def build_conversion_graph(checkpointer: Optional[MemorySaver] = None):
    graph = StateGraph(ConversionState)

    graph.add_node("validation_bootstrap", validation_bootstrap_node)
    graph.add_node("planner", planner_node)
    graph.add_node("supervisor", supervisor_node)

    graph.add_node("notebook_analysis", notebook_analysis_agent)
    graph.add_node("notebook_execution", notebook_execution_agent)
    graph.add_node("code_understanding", code_understanding_agent)
    graph.add_node("markdown", markdown_agent)
    graph.add_node("metadata", metadata_agent)
    graph.add_node("documentation", documentation_agent)
    graph.add_node("image_processing", image_processing_agent)
    graph.add_node("enrichment_merge", enrichment_merge_node)
    graph.add_node("coordinator", coordinator_agent)
    graph.add_node("validation", validation_agent)
    graph.add_node("quality_review", quality_review_agent)
    graph.add_node("pdf_assembly", pdf_assembly_agent)
    graph.add_node("packaging", packaging_agent)
    graph.add_node("finish", finish_node)
    graph.add_node("error_node", error_node)

    graph.add_edge(START, "validation_bootstrap")
    graph.add_conditional_edges(
        "validation_bootstrap",
        lambda s: "planner" if s.get("provider_ok") else "error_node",
        {"planner": "planner", "error_node": "error_node"},
    )
    graph.add_edge("planner", "supervisor")

    # AI supervisor -> workers (including Send fan-out for parallel_enrichment)
    graph.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "notebook_analysis": "notebook_analysis",
            "notebook_execution": "notebook_execution",
            "code_understanding": "code_understanding",
            "markdown": "markdown",
            "metadata": "metadata",
            "documentation": "documentation",
            "image_processing": "image_processing",
            "coordinator": "coordinator",
            "validation": "validation",
            "quality_review": "quality_review",
            "pdf_assembly": "pdf_assembly",
            "packaging": "packaging",
            "FINISH": "finish",
        },
    )

    # Parallel enrichment workers join via enrichment_merge
    for worker in (
        "code_understanding",
        "markdown",
        "metadata",
        "image_processing",
    ):
        graph.add_edge(worker, "enrichment_merge")
    graph.add_edge("enrichment_merge", "supervisor")

    # Sequential workers return to supervisor
    for worker in (
        "notebook_analysis",
        "notebook_execution",
        "documentation",
        "coordinator",
        "validation",
        "quality_review",
        "pdf_assembly",
        "packaging",
    ):
        graph.add_edge(worker, "supervisor")

    graph.add_edge("finish", END)
    graph.add_edge("error_node", "finish")

    return graph.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_compiled_graph():
    return build_conversion_graph(checkpointer=None)


def get_checkpointed_graph() -> Any:
    return build_conversion_graph(checkpointer=get_checkpointer())


def _initial_state(
    *,
    notebooks: List[NotebookInput],
    pdf_settings: Dict[str, Any],
    provider_id: str,
    api_key: str,
    model: str,
    auto_execute: bool,
    execution_timeout: int,
    thread_id: str,
) -> ConversionState:
    return {
        "notebooks": notebooks,
        "pdf_settings": pdf_settings,
        "provider_id": provider_id,
        "api_key": api_key,
        "model": model,
        "use_llm_enrichment": True,
        "auto_execute": auto_execute,
        "execution_timeout": execution_timeout,
        "quality_threshold": settings.quality_threshold,
        "max_repair_loops": settings.max_repair_loops,
        "thread_id": thread_id,
        "logs": [],
        "status": "pending",
        "error": None,
        "pdf_artifacts": [],
        "html_documents": [],
        "parsed": [],
        "analyses": [],
        "execution_reports": [],
        "needs_execution": False,
        "completed_steps": [],
        "plan_steps": [],
        "repair_loops": 0,
        "agent_memory": {},
        "messages": [],
        "readme_documents": [],
        "documentation_bundle": {},
    }


def run_conversion_graph(
    *,
    notebooks: List[NotebookInput],
    pdf_settings: Dict[str, Any],
    provider_id: str,
    api_key: str,
    model: str,
    use_llm_enrichment: bool = True,
    auto_execute: bool | None = None,
    execution_timeout: int | None = None,
    thread_id: str | None = None,
) -> ConversionState:
    """Invoke the AI-native supervisor graph (sole execution engine)."""
    del use_llm_enrichment  # always AI-native; kept for call-site compatibility
    tid = thread_id or f"pdf-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    app = get_checkpointed_graph()
    initial = _initial_state(
        notebooks=notebooks,
        pdf_settings=pdf_settings,
        provider_id=provider_id,
        api_key=api_key,
        model=model,
        auto_execute=(
            settings.auto_execute_notebooks if auto_execute is None else auto_execute
        ),
        execution_timeout=(
            settings.execution_timeout if execution_timeout is None else execution_timeout
        ),
        thread_id=tid,
    )
    logger.info(
        "Starting AI supervisor graph | files=%s | provider=%s",
        len(notebooks),
        provider_id,
    )
    remember_conversation(tid, {"event": "start", "files": len(notebooks)})
    config = {"configurable": {"thread_id": tid}, "recursion_limit": 80}
    final = app.invoke(initial, config=config)
    remember_conversation(
        tid,
        {
            "event": "end",
            "status": final.get("status"),
            "download": final.get("download_name"),
        },
    )
    return final  # type: ignore[return-value]


def stream_conversion_graph(
    *,
    notebooks: List[NotebookInput],
    pdf_settings: Dict[str, Any],
    provider_id: str,
    api_key: str,
    model: str,
    use_llm_enrichment: bool = True,
    auto_execute: bool | None = None,
    execution_timeout: int | None = None,
    thread_id: str | None = None,
) -> Iterator[Dict[str, Any]]:
    del use_llm_enrichment
    tid = thread_id or f"pdf-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    app = get_checkpointed_graph()
    initial = _initial_state(
        notebooks=notebooks,
        pdf_settings=pdf_settings,
        provider_id=provider_id,
        api_key=api_key,
        model=model,
        auto_execute=(
            settings.auto_execute_notebooks if auto_execute is None else auto_execute
        ),
        execution_timeout=(
            settings.execution_timeout if execution_timeout is None else execution_timeout
        ),
        thread_id=tid,
    )
    config = {"configurable": {"thread_id": tid}, "recursion_limit": 80}
    for event in app.stream(initial, config=config, stream_mode="updates"):
        yield event


def export_graph_mermaid() -> str:
    return graph_mermaid(get_compiled_graph())
