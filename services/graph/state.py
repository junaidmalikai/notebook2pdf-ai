"""LangGraph typed state for the AI-native multi-agent conversion system."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


def _merge_logs(left: List[str], right: List[str]) -> List[str]:
    return (left or []) + (right or [])


def _merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(left or {})
    out.update(right or {})
    return out


def _merge_parsed(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge parsed notebook rows by filename (parallel Send safe)."""
    by_file: Dict[str, Dict[str, Any]] = {}
    for item in (left or []) + (right or []):
        fn = item.get("filename")
        if not fn:
            continue
        prev = dict(by_file.get(fn) or {})
        for k, v in item.items():
            if v in (None, "", [], {}):
                continue
            prev[k] = v
        by_file[fn] = prev
    return list(by_file.values())


def _merge_notebooks(
    left: List[Dict[str, Any]],
    right: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge notebook payloads by filename (parallel Send safe)."""
    by_file: Dict[str, Dict[str, Any]] = {}
    for item in (left or []):
        fn = item.get("filename")
        if fn:
            by_file[fn] = dict(item)
    for item in (right or []):
        fn = item.get("filename")
        if not fn:
            continue
        by_file[fn] = dict(item)
    return list(by_file.values())


def _last_value(left: Any, right: Any) -> Any:
    """Last-write-wins for scalars / wholesale replacements under concurrency."""
    return right if right is not None else left


def _merge_dict_lists(
    left: List[Dict[str, Any]],
    right: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge list-of-dicts by filename when present; otherwise last-write-wins."""
    if not left:
        return list(right or [])
    if not right:
        return list(left or [])
    if all(isinstance(x, dict) and x.get("filename") for x in left + right):
        by_file: Dict[str, Dict[str, Any]] = {}
        for item in left + right:
            by_file[item["filename"]] = dict(item)
        return list(by_file.values())
    return list(right)


class NotebookInput(TypedDict):
    filename: str
    content: bytes


class ExecutionAnalysis(TypedDict, total=False):
    filename: str
    needs_execution: bool
    already_executed: bool
    unexecuted_code_cells: int
    executed_code_cells: int
    error_cells: int
    code_cells: int
    content_hash: str
    summary: str
    ai_summary: str
    ai_confidence: float
    ai_decision: str
    risks: List[str]


class ExecutionReport(TypedDict, total=False):
    filename: str
    executed: bool
    from_cache: bool
    cells_executed: int
    cells_failed: int
    success: bool
    error: Optional[str]
    verified: bool


class ParsedNotebook(TypedDict, total=False):
    filename: str
    title: str
    description: str
    language: str
    cell_count: int
    code_cells: int
    markdown_cells: int
    cells_html: str
    toc_html: str
    source_title: str
    keywords: List[str]
    executive_summary: str
    insights: List[str]
    features: List[str]
    readme_markdown: str
    architecture_notes: str
    code_explanation: str
    dependencies: List[str]
    code_understanding: Dict[str, Any]
    image_inventory: Dict[str, Any]
    markdown_notes: str
    markdown_score: int


class PdfArtifact(TypedDict):
    filename: str
    content: bytes
    title: str


class ConversionState(TypedDict, total=False):
    """Shared persistent state for the supervisor multi-agent graph."""

    # Parallel Send may touch notebooks (e.g. accidental full snapshots) — merge by name
    notebooks: Annotated[List[NotebookInput], _merge_notebooks]
    pdf_settings: Annotated[Dict[str, Any], _last_value]
    provider_id: Annotated[str, _last_value]
    api_key: Annotated[str, _last_value]
    model: Annotated[str, _last_value]
    use_llm_enrichment: Annotated[bool, _last_value]
    auto_execute: Annotated[bool, _last_value]
    execution_timeout: Annotated[int, _last_value]
    quality_threshold: Annotated[int, _last_value]
    max_repair_loops: Annotated[int, _last_value]
    thread_id: Annotated[str, _last_value]

    plan: Annotated[Dict[str, Any], _last_value]
    plan_steps: Annotated[List[str], _last_value]
    completed_steps: Annotated[List[str], operator.add]
    next_agent: Annotated[str, _last_value]
    supervisor_instructions: Annotated[str, _last_value]
    supervisor_reasoning: Annotated[str, _last_value]
    messages: Annotated[List[Any], operator.add]

    provider_ok: Annotated[bool, _last_value]
    analyses: Annotated[List[ExecutionAnalysis], _merge_dict_lists]
    execution_reports: Annotated[List[ExecutionReport], _merge_dict_lists]
    needs_execution: Annotated[bool, _last_value]
    parsed: Annotated[List[ParsedNotebook], _merge_parsed]
    # Isolated parallel branch payloads (optional; merged by enrichment_merge)
    code_result: Annotated[Dict[str, Any], _merge_dicts]
    markdown_result: Annotated[Dict[str, Any], _merge_dicts]
    metadata_result: Annotated[Dict[str, Any], _merge_dicts]
    image_result: Annotated[Dict[str, Any], _merge_dicts]
    html_documents: Annotated[List[str], _last_value]
    pdf_artifacts: Annotated[List[PdfArtifact], _last_value]
    readme_documents: Annotated[List[Dict[str, str]], _last_value]
    documentation_bundle: Annotated[Dict[str, Any], _merge_dicts]
    pdf_assembly_plan: Annotated[Dict[str, Any], _last_value]
    validation: Annotated[Dict[str, Any], _last_value]
    quality: Annotated[Dict[str, Any], _last_value]
    repair_loops: Annotated[int, _last_value]
    agent_memory: Annotated[Dict[str, Any], _merge_dicts]

    download_bytes: Annotated[Optional[bytes], _last_value]
    download_name: Annotated[str, _last_value]
    download_mime: Annotated[str, _last_value]
    is_batch: Annotated[bool, _last_value]
    pdf_count: Annotated[int, _last_value]

    logs: Annotated[List[str], _merge_logs]
    error: Annotated[Optional[str], _last_value]
    status: Annotated[str, _last_value]
