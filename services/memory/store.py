"""Checkpoint + in-process memory stores for multi-agent conversion."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver

from utils.logging_config import get_logger

logger = get_logger(__name__)

_CONVERSATION_MEMORY: Dict[str, list] = {}
_AGENT_MEMORY: Dict[str, Dict[str, Any]] = {}


@lru_cache(maxsize=1)
def get_checkpointer() -> MemorySaver:
    """Shared in-memory LangGraph checkpointer for recovery / resume."""
    return MemorySaver()


def remember_conversation(thread_id: str, event: Dict[str, Any]) -> None:
    _CONVERSATION_MEMORY.setdefault(thread_id, []).append(event)


def remember_agent(thread_id: str, agent: str, payload: Dict[str, Any]) -> None:
    bucket = _AGENT_MEMORY.setdefault(thread_id, {})
    prev = dict(bucket.get(agent) or {})
    prev.update(payload)
    bucket[agent] = prev
