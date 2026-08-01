"""AI-only Planner and Supervisor via LCEL structured chains. Zero heuristics."""

from __future__ import annotations

import json
from typing import Any, Dict

from services.agents.llm import get_llm
from services.agents.schemas import ConversionPlan, SupervisorDecision
from services.agents.session import AgentSession
from services.graph.chains import (
    build_planner_chain,
    build_supervisor_chain,
    invoke_chain_to_dict,
)
from services.graph.state import ConversionState
from utils.security import sanitize_error


def ai_plan(session: AgentSession, state: ConversionState) -> Dict[str, Any]:
    """Planner Agent: LCEL structured plan. Fails closed - no default / heuristic plan."""
    llm = get_llm(session.provider_id, session.api_key, session.model, temperature=0.0)
    try:
        raw = invoke_chain_to_dict(
            build_planner_chain(llm),
            {
                "notebooks": json.dumps(
                    [
                        {"filename": n["filename"], "size": len(n["content"])}
                        for n in session.notebooks
                    ]
                ),
                "auto_execute": session.auto_execute,
                "pdf_settings": json.dumps(
                    {
                        k: (session.pdf_settings or {}).get(k)
                        for k in ("title", "author", "company", "description")
                    }
                ),
                "threshold": session.quality_threshold,
            },
        )
        plan = ConversionPlan.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        session.error = f"AI Planner failed: {sanitize_error(exc)}"
        session.status = "error"
        return {
            "error": session.error,
            "status": "error",
            "logs": [f"planner: {session.error}"],
            "next_agent": "FINISH",
            "completed_steps": ["planner"],
        }

    # Trust the AI plan entirely (auto_execute is an input to the planner prompt).
    steps = list(plan.steps)
    session.log("planner", f"AI plan: {plan.rationale[:240]}")
    session.needs_execution = bool(plan.needs_execution) and bool(session.auto_execute)
    return {
        "plan": plan.model_dump(),
        "plan_steps": steps,
        "needs_execution": session.needs_execution,
        "next_agent": steps[0] if steps else "FINISH",
        "status": "running",
        "error": None,
        "logs": [
            f"planner: steps={steps} | execute={session.needs_execution} | {plan.rationale[:200]}"
        ],
        "completed_steps": ["planner"],
        "agent_memory": {"planner": plan.model_dump()},
    }


def ai_supervise(session: AgentSession, state: ConversionState) -> Dict[str, Any]:
    """Supervisor Agent: LCEL structured routing. Fails closed - no heuristic router."""
    llm = get_llm(session.provider_id, session.api_key, session.model, temperature=0.0)
    try:
        raw = invoke_chain_to_dict(
            build_supervisor_chain(llm),
            {
                "plan_steps": state.get("plan_steps") or [],
                "completed_steps": state.get("completed_steps") or [],
                "needs_execution": session.needs_execution,
                "quality": json.dumps(session.quality),
                "validation": json.dumps(session.validation),
                "repair_loops": session.repair_loops,
                "max_repair_loops": session.max_repair_loops,
                "status": session.status,
                "error": session.error,
                "has_pdfs": bool(session.pdf_artifacts),
                "has_download": bool(session.download_bytes),
            },
        )
        decision = SupervisorDecision.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        session.error = f"AI Supervisor failed: {sanitize_error(exc)}"
        session.status = "error"
        return {
            "error": session.error,
            "status": "error",
            "next_agent": "FINISH",
            "logs": [f"supervisor: {session.error}"],
            "completed_steps": ["supervisor"],
        }

    session.log("supervisor", f"next={decision.next_agent} | {decision.reasoning[:200]}")
    return {
        "next_agent": decision.next_agent,
        "supervisor_instructions": decision.instructions,
        "supervisor_reasoning": decision.reasoning,
        "logs": [f"supervisor: next={decision.next_agent} | {decision.reasoning[:220]}"],
        "completed_steps": ["supervisor"],
        "agent_memory": {
            "supervisor": {
                "next": decision.next_agent,
                "reasoning": decision.reasoning,
                "instructions": decision.instructions,
            }
        },
    }
