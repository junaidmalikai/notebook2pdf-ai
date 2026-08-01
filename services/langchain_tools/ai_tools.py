"""AI-oriented LangChain tool helpers: insights, dependencies, validation, images."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List

from utils.security import sanitize_error


def _decode_nb(content_b64: str) -> bytes:
    return base64.b64decode(content_b64)


def _dependency_tool(filename: str, content_b64: str) -> str:
    """Extract import / dependency hints from code cells."""
    try:
        payload = json.loads(_decode_nb(content_b64).decode("utf-8-sig"))
        imports: List[str] = []
        for cell in payload.get("cells") or []:
            if cell.get("cell_type") != "code":
                continue
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            for line in str(src).splitlines():
                s = line.strip()
                if s.startswith("import ") or s.startswith("from "):
                    imports.append(s)
        unique = sorted(set(imports))
        return json.dumps({"ok": True, "filename": filename, "imports": unique[:80]})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": sanitize_error(exc)})


def _output_inventory_tool(filename: str, content_b64: str) -> str:
    """Inventory stdout/stderr/errors/images/tables in notebook outputs."""
    try:
        payload = json.loads(_decode_nb(content_b64).decode("utf-8-sig"))
        stats = {
            "stdout": 0,
            "stderr": 0,
            "errors": 0,
            "images": 0,
            "html": 0,
            "tables": 0,
            "plotly_hints": 0,
        }
        for cell in payload.get("cells") or []:
            for out in cell.get("outputs") or []:
                if not isinstance(out, dict):
                    continue
                otype = out.get("output_type")
                if otype == "error":
                    stats["errors"] += 1
                elif otype == "stream":
                    if out.get("name") == "stderr":
                        stats["stderr"] += 1
                    else:
                        stats["stdout"] += 1
                data = out.get("data") or {}
                if not isinstance(data, dict):
                    continue
                for mime in data:
                    if str(mime).startswith("image/"):
                        stats["images"] += 1
                    if mime == "text/html":
                        stats["html"] += 1
                        html = data.get(mime)
                        if isinstance(html, list):
                            html = "".join(html)
                        lower = str(html).lower()
                        if "dataframe" in lower or "<table" in lower:
                            stats["tables"] += 1
                    if "plotly" in str(mime).lower():
                        stats["plotly_hints"] += 1
        return json.dumps({"ok": True, "filename": filename, **stats})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": sanitize_error(exc)})


def _image_inventory_tool(filename: str, content_b64: str) -> str:
    try:
        payload = json.loads(_decode_nb(content_b64).decode("utf-8-sig"))
        figures: List[Dict[str, Any]] = []
        missing = 0
        for idx, cell in enumerate(payload.get("cells") or []):
            for out in cell.get("outputs") or []:
                data = (out or {}).get("data") or {}
                if not isinstance(data, dict):
                    continue
                for mime, value in data.items():
                    if not str(mime).startswith("image/"):
                        continue
                    empty = value is None or value == "" or value == []
                    if empty:
                        missing += 1
                    figures.append(
                        {
                            "cell": idx,
                            "mime": mime,
                            "empty": empty,
                            "size_hint": 0 if value is None else len(str(value)),
                        }
                    )
        return json.dumps(
            {
                "ok": True,
                "filename": filename,
                "image_count": len(figures),
                "missing_payloads": missing,
                "figures": figures[:50],
            }
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": sanitize_error(exc)})


def _summary_tool(
    filename: str,
    title: str = "",
    description: str = "",
    code_cells: int = 0,
    markdown_cells: int = 0,
) -> str:
    """Deterministic structural summary used as tool evidence for AI agents."""
    return json.dumps(
        {
            "filename": filename,
            "title": title or filename.rsplit(".", 1)[0],
            "description": description,
            "code_cells": code_cells,
            "markdown_cells": markdown_cells,
            "summary": (
                f"{filename}: {code_cells} code / {markdown_cells} markdown cells. "
                f"{(description or '')[:240]}"
            ),
        }
    )


def _validation_tool(parsed_json: str, analyses_json: str = "[]", execution_json: str = "[]") -> str:
    parsed = json.loads(parsed_json or "[]")
    blocking: List[str] = []
    warnings: List[str] = []
    if not parsed:
        blocking.append("No parsed notebooks available for PDF assembly")
    for item in parsed:
        if not item.get("title"):
            warnings.append(f"{item.get('filename')}: missing title")
        if not item.get("cells_html") and item.get("cell_count", 0) == 0:
            warnings.append(f"{item.get('filename')}: empty body")
    for report in json.loads(execution_json or "[]"):
        if report.get("cells_failed"):
            warnings.append(
                f"{report.get('filename')}: {report.get('cells_failed')} cells failed during execution"
            )
    return json.dumps(
        {
            "ok": not blocking,
            "blocking_issues": blocking,
            "warnings": warnings,
            "ready_for_pdf": not blocking and bool(parsed),
        }
    )


def _insights_seed_tool(filename: str, excerpt: str = "", title: str = "") -> str:
    """Seed insight context for the Documentation / Code Understanding agents."""
    return json.dumps(
        {
            "filename": filename,
            "title": title,
            "excerpt": (excerpt or "")[:4000],
            "hint": "Use this excerpt with the AI documentation chain; do not invent results.",
        }
    )
