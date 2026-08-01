"""Factory for genuine LangChain / LangGraph tool-calling agents."""

from __future__ import annotations

from typing import Any, List, Sequence

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from services.agents.llm import get_llm
from utils.logging_config import get_logger
from utils.security import sanitize_error

logger = get_logger(__name__)


def build_tool_calling_agent(
    *,
    provider_id: str,
    api_key: str,
    model: str,
    tools: Sequence[BaseTool],
    system_prompt: str,
    name: str,
):
    """Create a ReAct / tool-calling agent. Prefers langchain.agents.create_agent."""
    llm = get_llm(provider_id, api_key, model, temperature=0.0)
    tool_list = list(tools)
    try:
        from langchain.agents import create_agent
        from langchain.agents.middleware import ToolRetryMiddleware

        return create_agent(
            model=llm,
            tools=tool_list,
            system_prompt=system_prompt,
            middleware=[ToolRetryMiddleware(max_retries=2)],
            name=name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("create_agent unavailable (%s); using create_react_agent", exc)
        try:
            return create_react_agent(llm, tools=tool_list, name=name)
        except TypeError:
            return create_react_agent(llm, tools=tool_list)


def run_tool_calling_agent(
    agent: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    recursion_limit: int = 25,
) -> dict:
    """
    Invoke a tool-calling agent. The LLM selects and calls tools autonomously.

    Returns message summary for logging; session mutation happens inside tools.
    """
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    try:
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": recursion_limit},
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Tool-calling agent failed: {sanitize_error(exc)}") from exc

    tool_calls: List[str] = []
    observations: List[str] = []
    final_text = ""
    for msg in result.get("messages") or []:
        if isinstance(msg, AIMessage) or getattr(msg, "type", "") == "ai":
            for c in getattr(msg, "tool_calls", None) or []:
                if isinstance(c, dict):
                    tool_calls.append(c.get("name") or "?")
                else:
                    tool_calls.append(getattr(c, "name", "?"))
            content = getattr(msg, "content", "") or ""
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text", part)) if isinstance(part, dict) else str(part)
                    for part in content
                )
            if str(content).strip():
                final_text = str(content).strip()
        elif isinstance(msg, ToolMessage) or getattr(msg, "type", "") == "tool":
            observations.append(str(getattr(msg, "content", ""))[:400])

    return {
        "tool_calls": tool_calls,
        "observations": observations[-8:],
        "final_text": final_text[:800],
    }
