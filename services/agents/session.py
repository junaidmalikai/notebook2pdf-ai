"""Mutable conversion session closed over by LangChain tools and agents."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentSession:
    """Shared working memory for all tool-calling agents in one conversion run."""

    notebooks: List[Dict[str, Any]]
    pdf_settings: Dict[str, Any]
    provider_id: str
    api_key: str
    model: str
    auto_execute: bool = True
    execution_timeout: int = 60
    quality_threshold: int = 72
    max_repair_loops: int = 2
    thread_id: str = "default"

    # Accumulators (tools write here)
    provider_ok: bool = False
    analyses: List[Dict[str, Any]] = field(default_factory=list)
    needs_execution: bool = False
    execution_reports: List[Dict[str, Any]] = field(default_factory=list)
    parsed: List[Dict[str, Any]] = field(default_factory=list)
    html_documents: List[str] = field(default_factory=list)
    pdf_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    readme_documents: List[Dict[str, str]] = field(default_factory=list)
    documentation_bundle: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)
    pdf_assembly_plan: Dict[str, Any] = field(default_factory=dict)
    download_bytes: Optional[bytes] = None
    download_name: str = ""
    download_mime: str = ""
    is_batch: bool = False
    pdf_count: int = 0
    logs: List[str] = field(default_factory=list)
    tool_trace: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    status: str = "pending"
    repair_loops: int = 0

    def log(self, agent: str, message: str) -> None:
        self.logs.append(f"{agent}: {message}")

    def trace_tool(self, name: str, detail: str) -> None:
        self.tool_trace.append({"tool": name, "detail": detail[:500]})

    def notebook_b64(self, filename: str) -> str:
        for nb in self.notebooks:
            if nb["filename"] == filename:
                return base64.b64encode(nb["content"]).decode("ascii")
        raise KeyError(f"Notebook not found: {filename}")

    def update_notebook_bytes(self, filename: str, content: bytes) -> None:
        for nb in self.notebooks:
            if nb["filename"] == filename:
                nb["content"] = content
                return
        raise KeyError(f"Notebook not found: {filename}")

    def upsert_parsed(self, filename: str, patch: Dict[str, Any]) -> None:
        for item in self.parsed:
            if item.get("filename") == filename:
                item.update({k: v for k, v in patch.items() if v is not None})
                return
        row = {"filename": filename}
        row.update(patch)
        self.parsed.append(row)

    def snapshot_for_graph(self, *, mode: str = "full") -> Dict[str, Any]:
        """
        Map session accumulators into ConversionState fields.

        mode='full'     - sequential nodes / coordinator merge (may include notebooks)
        mode='parallel' - Send fan-out workers: only reducer-safe / isolated keys
                          so concurrent updates never collide on notebooks.
        """
        if mode == "parallel":
            return {
                "parsed": list(self.parsed),
                "logs": list(self.logs),
                "agent_memory": {"tool_trace": list(self.tool_trace[-40:])},
            }
        return {
            "notebooks": [
                {"filename": n["filename"], "content": n["content"]} for n in self.notebooks
            ],
            "provider_ok": self.provider_ok,
            "analyses": list(self.analyses),
            "needs_execution": self.needs_execution,
            "execution_reports": list(self.execution_reports),
            "parsed": list(self.parsed),
            "html_documents": list(self.html_documents),
            "pdf_artifacts": list(self.pdf_artifacts),
            "readme_documents": list(self.readme_documents),
            "documentation_bundle": dict(self.documentation_bundle),
            "validation": dict(self.validation),
            "quality": dict(self.quality),
            "pdf_assembly_plan": dict(self.pdf_assembly_plan),
            "download_bytes": self.download_bytes,
            "download_name": self.download_name,
            "download_mime": self.download_mime,
            "is_batch": self.is_batch,
            "pdf_count": self.pdf_count,
            "logs": list(self.logs),
            "error": self.error,
            "status": self.status,
            "repair_loops": self.repair_loops,
            "agent_memory": {"tool_trace": list(self.tool_trace[-40:])},
        }
