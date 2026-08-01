"""Parse .ipynb JSON into typed NotebookDocument models."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Union

from utils.logging_config import get_logger

from .models import CellType, NotebookCell, NotebookDocument, NotebookOutput, OutputType

logger = get_logger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "".join(str(v) for v in value)
    return str(value)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _extract_images(data: Dict[str, Any]) -> List[Dict[str, str]]:
    images: List[Dict[str, str]] = []
    for mime in (
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/svg+xml",
        "image/gif",
        "image/webp",
    ):
        if mime not in data:
            continue
        raw = data[mime]
        payload = _as_text(raw).strip()
        if payload:
            images.append({"mime": mime, "data_b64": payload})
    return images


def _parse_output(raw: Dict[str, Any]) -> NotebookOutput | None:
    otype = raw.get("output_type", "")
    try:
        output_type = OutputType(otype)
    except ValueError:
        logger.debug("Skipping unknown output type: %s", otype)
        return None

    if output_type == OutputType.STREAM:
        return NotebookOutput(
            output_type=output_type,
            text=_strip_ansi(_as_text(raw.get("text", ""))),
            name=raw.get("name", "stdout"),
        )

    if output_type == OutputType.ERROR:
        return NotebookOutput(
            output_type=output_type,
            ename=raw.get("ename", "Error"),
            evalue=raw.get("evalue", ""),
            traceback=[_strip_ansi(t) for t in raw.get("traceback", [])],
            text=_strip_ansi("\n".join(raw.get("traceback", []))),
        )

    data = raw.get("data", {}) or {}
    text = _strip_ansi(_as_text(data.get("text/plain", "")))
    html = _as_text(data.get("text/html", ""))
    images = _extract_images(data)

    # Plotly JSON → leave note; static PNG may already be present
    if "application/vnd.plotly.v1+json" in data and not images:
        text = text or "[Plotly figure — static image not available in notebook outputs]"

    return NotebookOutput(
        output_type=output_type,
        text=text,
        html=html,
        images=images,
        data={k: ("<omitted>" if k.startswith("image/") or "plotly" in k else v)
              for k, v in data.items()},
    )


def _is_hidden(metadata: Dict[str, Any]) -> bool:
    if metadata.get("jupyter", {}).get("source_hidden"):
        return True
    tags = metadata.get("tags", []) or []
    return any(t in {"hide", "hidden", "remove_cell"} for t in tags)


def _is_collapsed(metadata: Dict[str, Any]) -> bool:
    if metadata.get("jupyter", {}).get("outputs_hidden"):
        return True
    return bool(metadata.get("collapsed"))


def _infer_title(filename: str, cells: List[NotebookCell], nb_meta: Dict[str, Any]) -> str:
    for key in ("title", "name"):
        if nb_meta.get(key):
            return str(nb_meta[key])
    for cell in cells:
        if cell.heading_level == 1 and cell.heading_text:
            return cell.heading_text
    return Path(filename).stem.replace("_", " ").replace("-", " ").title()


def _infer_description(cells: List[NotebookCell]) -> str:
    for cell in cells:
        if cell.cell_type != CellType.MARKDOWN:
            continue
        lines = []
        for line in cell.source.splitlines():
            s = line.strip()
            if (
                not s
                or s.startswith("#")
                or s.startswith("![")
                or s.startswith("|")
                or s.startswith("-")
                or s.startswith("*")
                or s.startswith(">")
                or s.startswith("[")
            ):
                continue
            lines.append(s)
            if len(" ".join(lines)) > 40:
                break
        if lines:
            desc = " ".join(lines)
            return desc[:280] + ("…" if len(desc) > 280 else "")
    return ""


def parse_notebook(
    data: Union[bytes, str, Dict[str, Any]],
    filename: str = "notebook.ipynb",
) -> NotebookDocument:
    """Parse notebook bytes/JSON into a NotebookDocument."""
    if isinstance(data, bytes):
        payload = json.loads(data.decode("utf-8-sig"))
    elif isinstance(data, str):
        payload = json.loads(data.lstrip("\ufeff"))
    else:
        payload = data

    if not isinstance(payload, dict) or "cells" not in payload:
        raise ValueError("Invalid notebook: missing 'cells' array.")

    meta = payload.get("metadata", {}) or {}
    kernelspec = meta.get("kernelspec", {}) or {}
    language_info = meta.get("language_info", {}) or {}
    language = (
        language_info.get("name")
        or kernelspec.get("language")
        or "python"
    )

    cells: List[NotebookCell] = []
    for idx, raw_cell in enumerate(payload.get("cells", [])):
        ctype_raw = raw_cell.get("cell_type", "raw")
        try:
            ctype = CellType(ctype_raw)
        except ValueError:
            ctype = CellType.RAW

        cell_meta = raw_cell.get("metadata", {}) or {}
        outputs = []
        if ctype == CellType.CODE:
            for o in raw_cell.get("outputs", []) or []:
                parsed = _parse_output(o)
                if parsed:
                    outputs.append(parsed)

        cells.append(
            NotebookCell(
                cell_type=ctype,
                source=_as_text(raw_cell.get("source", "")),
                execution_count=raw_cell.get("execution_count"),
                outputs=outputs,
                metadata=cell_meta,
                hidden=_is_hidden(cell_meta),
                collapsed=_is_collapsed(cell_meta),
                index=idx,
            )
        )

    title = _infer_title(filename, cells, meta)
    description = _infer_description(cells)

    return NotebookDocument(
        filename=filename,
        cells=cells,
        metadata=meta,
        nbformat=int(payload.get("nbformat", 4)),
        title=title,
        description=description,
        language=str(language),
    )
