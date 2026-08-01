"""Compliance + import smoke audit for AI-native architecture."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def main() -> None:
    checks: list[tuple[str, bool, str]] = []

    planner = _read("services/agents/planner_supervisor.py")
    agent_entry = _read("services/agent.py")
    workflow = _read("services/graph/workflow.py")
    bound = _read("services/agents/bound_tools.py")
    nodes = _read("services/agents/worker_nodes.py")
    chains = _read("services/graph/chains.py")

    checks.append(
        (
            "No _default_plan heuristic",
            "_default_plan" not in planner and "_default_plan" not in nodes,
            "planner/workers must not define heuristic plans",
        )
    )
    checks.append(
        (
            "No _heuristic_supervisor",
            "_heuristic_supervisor" not in planner and "_heuristic_supervisor" not in nodes,
            "supervisor must be AI-only",
        )
    )
    checks.append(
        (
            "No ThreadPoolExecutor orchestration",
            "from concurrent.futures import ThreadPoolExecutor" not in nodes
            and "ThreadPoolExecutor(" not in nodes,
            "parallelism must use LangGraph Send",
        )
    )
    checks.append(
        (
            "LangGraph Send used",
            "Send(" in nodes and "parallel_enrichment" in nodes,
            "parallel_enrichment must expand via Send",
        )
    )
    checks.append(
        (
            "Tool-calling agents",
            "build_tool_calling_agent" in nodes and "run_tool_calling_agent" in nodes,
            "workers must invoke create_agent/create_react_agent",
        )
    )
    checks.append(
        (
            "Single pipeline (no fallback pipeline)",
            "fallback" not in agent_entry.lower(),
            "agent.py must not run secondary conversion pipelines",
        )
    )
    checks.append(
        (
            "No keyword execution decision parsing",
            '"true" in reason.lower()' not in bound
            and "not required" not in bound,
            "set_execution_decision must use structured boolean",
        )
    )
    checks.append(
        (
            "Final approval tool present",
            "write_final_approval" in bound,
            "quality review must expose AI final approval",
        )
    )
    checks.append(
        (
            "No planner step-stripping override",
            'steps = [s for s in steps if s != "notebook_execution"]' not in planner,
            "planner must not hardcode step removal in Python",
        )
    )
    checks.append(
        (
            "No supervisor download short-circuit heuristic",
            "Download already packaged" not in planner,
            "supervisor must AI-route FINISH",
        )
    )
    checks.append(
        (
            "LCEL planner/supervisor chains",
            "build_planner_chain" in planner and "build_supervisor_chain" in planner,
            "planner/supervisor must use LCEL chains",
        )
    )
    for name in (
        "RunnableParallel",
        "RunnableBranch",
        "RunnableAssign",
        "RunnableLambda",
        "RunnablePassthrough",
        "RunnableSequence",
    ):
        checks.append((f"LCEL {name} defined", name in chains, f"{name} must exist in chains.py"))

    for name in (
        "lcel_metadata_enrichment",
        "lcel_code_insights",
        "lcel_readme_generation",
        "lcel_markdown_review",
        "lcel_quality_review",
        "lcel_parallel_enrichment",
    ):
        checks.append((f"LCEL tool {name}", name in bound, f"{name} must be a live tool"))

    checks.append(
        (
            "README packaging",
            "readme_documents" in bound and "_README.md" in bound,
            "README must be staged for download package",
        )
    )
    checks.append(
        (
            "Documentation packaging",
            "_DOCUMENTATION.md" in bound,
            "Documentation bundle must be packaged",
        )
    )
    checks.append(
        (
            "Workflow uses worker_nodes",
            "validation_bootstrap" in workflow and "enrichment_merge" in workflow,
            "graph must wire bootstrap + merge",
        )
    )

    try:
        from services.graph.workflow import export_graph_mermaid, get_compiled_graph
        from services.langchain_tools import list_tools

        g = get_compiled_graph()
        mermaid = export_graph_mermaid()
        tools = list_tools()
        checks.append(("Graph compiles", True, type(g).__name__))
        checks.append(("Mermaid has supervisor", "supervisor" in mermaid, "missing supervisor"))
        checks.append(("Mermaid has workers", "code_understanding" in mermaid, "missing workers"))
        checks.append(("Tools registered", len(tools) >= 20, f"count={len(tools)}"))
        checks.append(("No empty tool registry", bool(tools), "empty tools"))
    except Exception as exc:  # noqa: BLE001
        checks.append(("Import/compile", False, str(exc)))

    print("=" * 72)
    print("AI-NATIVE COMPLIANCE AUDIT")
    print("=" * 72)
    failed = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{status}] {name} :: {detail}")
    print("=" * 72)
    print(f"RESULT: {'ALL PASS' if failed == 0 else str(failed) + ' FAILED'}")
    raise SystemExit(failed)


if __name__ == "__main__":
    main()
