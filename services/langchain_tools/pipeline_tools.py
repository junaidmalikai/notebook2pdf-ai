"""Active LangChain tool registry for the AI-native conversion system."""

from __future__ import annotations

from typing import Dict, List

from langchain_core.tools import StructuredTool

from services.agents.bound_tools import all_registered_tool_names, build_session_tools
from services.agents.session import AgentSession


def _discovery_session() -> AgentSession:
    return AgentSession(
        notebooks=[],
        pdf_settings={},
        provider_id="openai",
        api_key="discover",
        model="gpt-4o-mini",
    )


def build_pipeline_tools() -> List[StructuredTool]:
    """All tools used by worker agents (union across roles)."""
    toolkits = build_session_tools(_discovery_session())
    by_name: Dict[str, StructuredTool] = {}
    for tools in toolkits.values():
        for t in tools:
            by_name[t.name] = t
    return list(by_name.values())


TOOL_REGISTRY: Dict[str, StructuredTool] = {t.name: t for t in build_pipeline_tools()}


def get_tool(name: str) -> StructuredTool:
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]


def list_tools() -> List[str]:
    return all_registered_tool_names(build_session_tools(_discovery_session()))
