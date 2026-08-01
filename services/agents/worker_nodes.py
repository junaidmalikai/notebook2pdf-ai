"""LangGraph worker nodes: each runs a genuine tool-calling agent.

Pattern:
  LLM decides tools -> Tool Calling -> Observation -> Reasoning -> Next Tool
Python never selects business tools on behalf of the agent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langgraph.types import Send

from services.agents.bound_tools import build_session_tools
from services.agents.planner_supervisor import ai_plan, ai_supervise
from services.agents.prompts import (
    CODE_UNDERSTANDING_PROMPT,
    COORDINATOR_PROMPT,
    DOCUMENTATION_PROMPT,
    IMAGE_PROCESSING_PROMPT,
    MARKDOWN_PROMPT,
    METADATA_PROMPT,
    NOTEBOOK_ANALYSIS_PROMPT,
    NOTEBOOK_EXECUTION_PROMPT,
    PACKAGING_PROMPT,
    PDF_ASSEMBLY_PROMPT,
    QUALITY_REVIEW_PROMPT,
    VALIDATION_PROMPT,
)
from services.agents.react import build_tool_calling_agent, run_tool_calling_agent
from services.agents.session import AgentSession
from services.graph.state import ConversionState
from services.memory import remember_agent, remember_conversation
from utils.logging_config import get_logger
from utils.security import sanitize_error

logger = get_logger(__name__)

# Weakref-like process map: thread_id -> AgentSession (single conversion)
_SESSIONS: Dict[str, AgentSession] = {}

# Roles that run under LangGraph Send fan-out (must not write notebooks concurrently)
_PARALLEL_ROLES = frozenset(
    {
        "code_understanding",
        "markdown",
        "metadata",
        "image_processing",
    }
)

_PARALLEL_RESULT_KEY = {
    "code_understanding": "code_result",
    "markdown": "markdown_result",
    "metadata": "metadata_result",
    "image_processing": "image_result",
}

WORKER_PROMPTS: Dict[str, str] = {
    "validation_bootstrap": VALIDATION_PROMPT
    + "\n\nYou MUST call validate_api, then list_uploaded_notebooks. Stop after tools confirm readiness.",
    "notebook_analysis": NOTEBOOK_ANALYSIS_PROMPT,
    "notebook_execution": NOTEBOOK_EXECUTION_PROMPT,
    "code_understanding": CODE_UNDERSTANDING_PROMPT,
    "markdown": MARKDOWN_PROMPT,
    "metadata": METADATA_PROMPT,
    "documentation": DOCUMENTATION_PROMPT,
    "image_processing": IMAGE_PROCESSING_PROMPT,
    "coordinator": COORDINATOR_PROMPT,
    "validation": VALIDATION_PROMPT
    + "\n\nCall validation_tool then write_validation with your judgment.",
    "quality_review": QUALITY_REVIEW_PROMPT,
    "pdf_assembly": PDF_ASSEMBLY_PROMPT,
    "packaging": PACKAGING_PROMPT,
}


def attach_session(state: ConversionState) -> AgentSession:
    tid = state.get("thread_id") or "default"
    session = _SESSIONS.get(tid)
    if session is None:
        session = AgentSession(
            notebooks=[
                {"filename": n["filename"], "content": n["content"]}
                for n in (state.get("notebooks") or [])
            ],
            pdf_settings=dict(state.get("pdf_settings") or {}),
            provider_id=state.get("provider_id") or "",
            api_key=state.get("api_key") or "",
            model=state.get("model") or "",
            auto_execute=bool(state.get("auto_execute", True)),
            execution_timeout=int(state.get("execution_timeout") or 60),
            quality_threshold=int(state.get("quality_threshold") or 72),
            max_repair_loops=int(state.get("max_repair_loops") or 2),
            thread_id=tid,
        )
        _SESSIONS[tid] = session
    else:
        # Keep notebooks/settings in sync if graph state advanced
        if state.get("notebooks"):
            session.notebooks = [
                {"filename": n["filename"], "content": n["content"]}
                for n in state["notebooks"]
            ]
    return session


def clear_session(thread_id: str) -> None:
    _SESSIONS.pop(thread_id, None)


def _run_role(state: ConversionState, role: str, user_extra: str = "") -> Dict[str, Any]:
    session = attach_session(state)
    toolkits = build_session_tools(session)
    tools = toolkits[role]
    prompt = WORKER_PROMPTS[role]
    names = [n["filename"] for n in session.notebooks]
    instructions = state.get("supervisor_instructions") or ""
    user_prompt = (
        f"Role: {role}\n"
        f"Notebooks: {names}\n"
        f"Supervisor instructions: {instructions}\n"
        f"Auto-execute: {session.auto_execute}\n"
        f"Quality threshold: {session.quality_threshold}\n"
        f"{user_extra}\n"
        "Use tools to complete your responsibilities. Do not invent tool results."
    )
    parallel = role in _PARALLEL_ROLES
    snap_mode = "parallel" if parallel else "full"
    try:
        agent = build_tool_calling_agent(
            provider_id=session.provider_id,
            api_key=session.api_key,
            model=session.model,
            tools=tools,
            system_prompt=prompt,
            name=f"{role}_agent",
        )
        summary = run_tool_calling_agent(
            agent, system_prompt=prompt, user_prompt=user_prompt
        )
        session.log(
            role,
            f"tools={summary['tool_calls']} | {summary.get('final_text', '')[:180]}",
        )
        remember_agent(session.thread_id, role, {"tool_calls": summary["tool_calls"]})
        out = session.snapshot_for_graph(mode=snap_mode)
        out["logs"] = [f"{role}: tools -> {summary['tool_calls']}"]
        if summary.get("final_text"):
            out["logs"].append(f"{role}: {summary['final_text'][:240]}")
        out["completed_steps"] = [role]
        # Isolated parallel payload (merged by enrichment_merge; never writes notebooks)
        if parallel:
            result_key = _PARALLEL_RESULT_KEY[role]
            out[result_key] = {
                "role": role,
                "tool_calls": summary.get("tool_calls") or [],
                "final_text": summary.get("final_text") or "",
                "ok": True,
            }
        return out
    except Exception as exc:  # noqa: BLE001
        msg = sanitize_error(exc)
        logger.exception("Worker %s failed", role)
        session.error = msg
        session.status = "error"
        if parallel:
            result_key = _PARALLEL_RESULT_KEY[role]
            return {
                "parsed": list(session.parsed),
                "logs": [f"{role}: FAILED {msg}"],
                "completed_steps": [role],
                "agent_memory": {role: {"error": msg}},
                result_key: {"role": role, "ok": False, "error": msg},
            }
        return {
            **session.snapshot_for_graph(mode="full"),
            "error": msg,
            "status": "error",
            "logs": [f"{role}: FAILED {msg}"],
            "completed_steps": [role],
        }


# ?? Graph nodes ??????????????????????????????????????????????????????????????


def validation_bootstrap_node(state: ConversionState) -> Dict[str, Any]:
    # Fresh session per run
    tid = state.get("thread_id") or "default"
    clear_session(tid)
    if not (state.get("provider_id") and state.get("api_key")):
        return {
            "provider_ok": False,
            "error": "Please enter a valid API key to continue.",
            "status": "error",
            "logs": ["validation_bootstrap: missing credentials"],
            "next_agent": "FINISH",
            "completed_steps": ["validation_bootstrap"],
        }
    out = _run_role(state, "validation_bootstrap")
    session = attach_session(state)
    if not session.provider_ok:
        out["status"] = "error"
        out["error"] = session.error or "API key validation failed"
        out["provider_ok"] = False
        out["next_agent"] = "FINISH"
    else:
        out["provider_ok"] = True
    return out


def planner_node(state: ConversionState) -> Dict[str, Any]:
    session = attach_session(state)
    if not session.notebooks:
        session.error = "No notebooks uploaded."
        session.status = "error"
        return {
            "error": session.error,
            "status": "error",
            "next_agent": "FINISH",
            "logs": ["planner: empty uploads"],
            "completed_steps": ["planner"],
        }
    return ai_plan(session, state)


def supervisor_node(state: ConversionState) -> Dict[str, Any]:
    session = attach_session(state)
    # Sync repair counters / quality from graph if workers updated session
    if state.get("quality"):
        session.quality = dict(state["quality"])
    return ai_supervise(session, state)


def notebook_analysis_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "notebook_analysis")


def notebook_execution_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "notebook_execution")


def code_understanding_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "code_understanding")


def markdown_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "markdown")


def metadata_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "metadata")


def documentation_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "documentation")


def image_processing_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "image_processing")


def coordinator_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "coordinator")


def validation_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "validation")


def quality_review_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(
        state,
        "quality_review",
        user_extra=(
            f"Threshold={attach_session(state).quality_threshold}. "
            f"Repair loops so far={attach_session(state).repair_loops}."
        ),
    )


def pdf_assembly_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "pdf_assembly")


def packaging_agent(state: ConversionState) -> Dict[str, Any]:
    return _run_role(state, "packaging")


def finish_node(state: ConversionState) -> Dict[str, Any]:
    session = attach_session(state)
    remember_conversation(
        session.thread_id,
        {"event": "finish", "status": session.status, "download": session.download_name},
    )
    if session.download_bytes and session.status != "error":
        session.status = "ok"
        return {
            **session.snapshot_for_graph(),
            "status": "ok",
            "logs": ["finish: conversion complete"],
        }
    if session.error:
        return {
            **session.snapshot_for_graph(),
            "status": "error",
            "logs": [f"finish: failed: {session.error}"],
        }
    return {
        **session.snapshot_for_graph(),
        "status": "error",
        "error": session.error or "Conversion finished without download payload",
        "logs": ["finish: missing download"],
    }


def error_node(state: ConversionState) -> Dict[str, Any]:
    session = attach_session(state)
    err = state.get("error") or session.error or "Unknown conversion error"
    session.error = err
    session.status = "error"
    return {
        "status": "error",
        "error": err,
        "logs": [f"error: {err}"],
        "next_agent": "FINISH",
    }


# ?? Routing (AI decision already stored in state.next_agent) ?????????????????


_PARALLEL_WORKERS = (
    "code_understanding",
    "markdown",
    "metadata",
    "image_processing",
)

_SINGLE_WORKERS = {
    "notebook_analysis",
    "notebook_execution",
    "code_understanding",
    "markdown",
    "metadata",
    "documentation",
    "image_processing",
    "coordinator",
    "validation",
    "quality_review",
    "pdf_assembly",
    "packaging",
    "FINISH",
}


def route_supervisor(state: ConversionState):
    """
    Map AI supervisor decision to LangGraph destinations.

    parallel_enrichment expands to LangGraph Send fan-out (native graph parallelism).
    """
    nxt = state.get("next_agent") or "FINISH"
    if nxt == "parallel_enrichment":
        return [Send(worker, state) for worker in _PARALLEL_WORKERS]
    if nxt in _SINGLE_WORKERS:
        return nxt
    # Invalid AI output -> finish with error path via finish
    return "FINISH"


def enrichment_merge_node(state: ConversionState) -> Dict[str, Any]:
    """
    Single writer after parallel Send workers.

    Combines isolated branch results already reduced into state, then publishes
    the authoritative session snapshot (including notebooks) once.
    """
    session = attach_session(state)
    # Ensure graph-parsed merges (from parallel workers) are visible in session
    if state.get("parsed"):
        for item in state["parsed"]:
            fn = item.get("filename")
            if fn:
                session.upsert_parsed(fn, dict(item))

    branches = {
        "code_understanding": state.get("code_result") or {},
        "markdown": state.get("markdown_result") or {},
        "metadata": state.get("metadata_result") or {},
        "image_processing": state.get("image_result") or {},
    }
    done = [name for name, payload in branches.items() if payload]
    session.log(
        "parallel_enrichment",
        f"LangGraph Send branches merged: {', '.join(done) or 'none'}",
    )
    out = session.snapshot_for_graph(mode="full")
    out["logs"] = [
        f"parallel_enrichment: merged Send branches ({', '.join(done) or 'passthrough'})"
    ]
    out["completed_steps"] = ["parallel_enrichment"]
    out["agent_memory"] = {"parallel_enrichment": {"branches": done}}
    return out
