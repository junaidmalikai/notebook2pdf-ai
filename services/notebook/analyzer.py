"""Analyze Jupyter notebooks to decide whether cell execution is required."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CellExecutionStatus:
    index: int
    cell_type: str
    hidden: bool = False
    execution_count: Optional[int] = None
    has_outputs: bool = False
    has_error: bool = False
    is_empty_source: bool = False
    needs_execution: bool = False
    reason: str = ""


@dataclass
class NotebookAnalysis:
    """Result of inspecting a notebook's execution readiness."""

    filename: str
    total_cells: int = 0
    code_cells: int = 0
    markdown_cells: int = 0
    raw_cells: int = 0
    hidden_cells: int = 0
    executed_code_cells: int = 0
    unexecuted_code_cells: int = 0
    error_cells: int = 0
    empty_code_cells: int = 0
    needs_execution: bool = False
    already_executed: bool = True
    content_hash: str = ""
    cells: List[CellExecutionStatus] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "total_cells": self.total_cells,
            "code_cells": self.code_cells,
            "markdown_cells": self.markdown_cells,
            "raw_cells": self.raw_cells,
            "hidden_cells": self.hidden_cells,
            "executed_code_cells": self.executed_code_cells,
            "unexecuted_code_cells": self.unexecuted_code_cells,
            "error_cells": self.error_cells,
            "empty_code_cells": self.empty_code_cells,
            "needs_execution": self.needs_execution,
            "already_executed": self.already_executed,
            "content_hash": self.content_hash,
            "summary": self.summary,
            "cells": [
                {
                    "index": c.index,
                    "cell_type": c.cell_type,
                    "hidden": c.hidden,
                    "execution_count": c.execution_count,
                    "has_outputs": c.has_outputs,
                    "has_error": c.has_error,
                    "is_empty_source": c.is_empty_source,
                    "needs_execution": c.needs_execution,
                    "reason": c.reason,
                }
                for c in self.cells
            ],
        }


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "".join(str(v) for v in value)
    return str(value)


def _is_hidden(metadata: Dict[str, Any]) -> bool:
    if metadata.get("jupyter", {}).get("source_hidden"):
        return True
    tags = metadata.get("tags", []) or []
    return any(t in {"hide", "hidden", "remove_cell"} for t in tags)


def notebook_content_hash(payload: Dict[str, Any]) -> str:
    """
    Stable hash of notebook *source* (not outputs).

    Changing cell source invalidates the execution cache; output-only
    differences do not.
    """
    digest_parts: List[str] = []
    for cell in payload.get("cells", []) or []:
        ctype = cell.get("cell_type", "")
        source = _as_text(cell.get("source", ""))
        digest_parts.append(f"{ctype}|{source}")
    blob = "\n".join(digest_parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _load_payload(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(data, bytes):
        return json.loads(data.decode("utf-8-sig"))
    if isinstance(data, str):
        return json.loads(data.lstrip("\ufeff"))
    return data


def analyze_notebook(
    data: Union[bytes, str, Dict[str, Any]],
    filename: str = "notebook.ipynb",
) -> NotebookAnalysis:
    """
    Inspect every cell and decide whether automatic execution is required.

    A code cell needs execution when it has non-empty source and either:
    - missing execution_count, or
    - empty / missing outputs (and is not intentionally empty).
    Error outputs count as "executed" (outputs exist) but are flagged.
    """
    payload = _load_payload(data)
    cells_raw = payload.get("cells", []) or []
    analysis = NotebookAnalysis(
        filename=filename,
        total_cells=len(cells_raw),
        content_hash=notebook_content_hash(payload),
    )

    for idx, raw in enumerate(cells_raw):
        ctype = str(raw.get("cell_type", "raw"))
        meta = raw.get("metadata", {}) or {}
        hidden = _is_hidden(meta)
        if hidden:
            analysis.hidden_cells += 1

        status = CellExecutionStatus(
            index=idx,
            cell_type=ctype,
            hidden=hidden,
        )

        if ctype == "markdown":
            analysis.markdown_cells += 1
            analysis.cells.append(status)
            continue

        if ctype != "code":
            analysis.raw_cells += 1
            analysis.cells.append(status)
            continue

        analysis.code_cells += 1
        source = _as_text(raw.get("source", "")).strip()
        status.is_empty_source = not bool(source)
        status.execution_count = raw.get("execution_count")
        outputs = raw.get("outputs", []) or []
        status.has_outputs = len(outputs) > 0
        status.has_error = any(
            isinstance(o, dict) and o.get("output_type") == "error" for o in outputs
        )
        if status.has_error:
            analysis.error_cells += 1

        if status.is_empty_source:
            analysis.empty_code_cells += 1
            status.needs_execution = False
            status.reason = "empty source"
        elif status.execution_count is None and not status.has_outputs:
            status.needs_execution = True
            status.reason = "never executed"
            analysis.unexecuted_code_cells += 1
        elif not status.has_outputs:
            # Executed count present but outputs wiped / interrupted
            status.needs_execution = True
            status.reason = "missing outputs"
            analysis.unexecuted_code_cells += 1
        else:
            status.needs_execution = False
            status.reason = "has outputs"
            analysis.executed_code_cells += 1

        analysis.cells.append(status)

    analysis.needs_execution = analysis.unexecuted_code_cells > 0
    analysis.already_executed = not analysis.needs_execution
    analysis.summary = (
        f"{filename}: {analysis.code_cells} code | "
        f"{analysis.executed_code_cells} executed | "
        f"{analysis.unexecuted_code_cells} pending | "
        f"{analysis.error_cells} errors | "
        f"{'EXECUTE' if analysis.needs_execution else 'SKIP'}"
    )
    logger.info(analysis.summary)
    return analysis
