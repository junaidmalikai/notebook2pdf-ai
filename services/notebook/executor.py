"""Isolated Jupyter notebook execution engine (nbclient / jupyter_client).

AI agents decide WHEN to execute; this module performs the actual run.
Never executes arbitrary code in the Streamlit main process - uses a
subprocess + temporary working directory with timeouts and cleanup.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from utils.logging_config import get_logger

from .analyzer import notebook_content_hash

logger = get_logger(__name__)

# In-process execution cache: content_hash -> executed notebook JSON bytes
_EXEC_CACHE: Dict[str, bytes] = {}
_CACHE_MAX = 32


@dataclass
class ExecutionResult:
    """Outcome of running a notebook through the execution engine."""

    success: bool
    notebook_bytes: bytes
    filename: str
    executed: bool = False
    from_cache: bool = False
    cells_executed: int = 0
    cells_failed: int = 0
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "filename": self.filename,
            "executed": self.executed,
            "from_cache": self.from_cache,
            "cells_executed": self.cells_executed,
            "cells_failed": self.cells_failed,
            "error": self.error,
            "logs": list(self.logs),
            "content_hash": self.content_hash,
            "notebook_bytes": self.notebook_bytes,
        }


def _load_nb(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(data, bytes):
        return json.loads(data.decode("utf-8-sig"))
    if isinstance(data, str):
        return json.loads(data.lstrip("\ufeff"))
    return dict(data)


def _cache_get(content_hash: str) -> Optional[bytes]:
    return _EXEC_CACHE.get(content_hash)


def _cache_put(content_hash: str, notebook_bytes: bytes) -> None:
    if len(_EXEC_CACHE) >= _CACHE_MAX:
        # Drop an arbitrary oldest entry (insertion-ordered dict)
        oldest = next(iter(_EXEC_CACHE))
        _EXEC_CACHE.pop(oldest, None)
    _EXEC_CACHE[content_hash] = notebook_bytes


def _count_code_failures(nb: Dict[str, Any]) -> tuple[int, int]:
    executed = 0
    failed = 0
    for cell in nb.get("cells", []) or []:
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if not str(source).strip():
            continue
        outputs = cell.get("outputs", []) or []
        if cell.get("execution_count") is not None or outputs:
            executed += 1
        if any(
            isinstance(o, dict) and o.get("output_type") == "error" for o in outputs
        ):
            failed += 1
    return executed, failed


def _notebook_to_dict(notebook: Any) -> Dict[str, Any]:
    """Convert NotebookNode / mixed structures to a plain JSON-safe dict."""
    if isinstance(notebook, dict):
        # NotebookNode is a dict subclass; json round-trip normalizes values
        return json.loads(json.dumps(notebook, default=lambda o: getattr(o, "__dict__", str(o))))
    try:
        import nbformat

        return json.loads(nbformat.writes(notebook))
    except Exception:  # noqa: BLE001
        return dict(notebook)


def _normalize_notebook_payload(nb: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure sources are strings and required nbformat fields exist."""
    payload = json.loads(json.dumps(nb))
    payload.setdefault("nbformat", 4)
    payload.setdefault("nbformat_minor", 5)
    payload.setdefault("metadata", {})
    cells = []
    for cell in payload.get("cells", []) or []:
        cell = dict(cell)
        src = cell.get("source", "")
        if isinstance(src, list):
            cell["source"] = "".join(str(x) for x in src)
        elif src is None:
            cell["source"] = ""
        else:
            cell["source"] = str(src)
        if cell.get("cell_type") == "code":
            cell.setdefault("outputs", [])
            cell.setdefault("execution_count", None)
        cell.setdefault("metadata", {})
        cells.append(cell)
    payload["cells"] = cells
    return payload


def _execute_with_nbclient(
    nb: Dict[str, Any],
    *,
    timeout: int,
    workdir: Path,
) -> Dict[str, Any]:
    """Run notebook in-process via nbclient (called from worker context)."""
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    payload = _normalize_notebook_payload(nb)
    notebook = nbformat.from_dict(payload)
    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name=_resolve_kernel_name(payload),
        resources={"metadata": {"path": str(workdir)}},
        allow_errors=True,  # capture tracebacks; continue remaining cells
        store_widget_state=False,
    )
    try:
        client.execute()
    except CellExecutionError:
        # allow_errors=True should prevent this; keep partial notebook
        logger.warning("CellExecutionError raised despite allow_errors")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notebook execution interrupted: %s", exc)
        # Attach a synthetic error on first unexecuted code cell if needed
        _annotate_fatal(notebook, exc)
    return _notebook_to_dict(notebook)


def _resolve_kernel_name(nb: Dict[str, Any]) -> str:
    meta = nb.get("metadata", {}) or {}
    kernelspec = meta.get("kernelspec", {}) or {}
    name = kernelspec.get("name") or "python3"
    return str(name)


def _annotate_fatal(nb: Any, exc: Exception) -> None:
    """Best-effort: record fatal kernel failure on the first code cell without outputs."""
    try:
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            outputs = cell.get("outputs") or []
            if outputs:
                continue
            tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
            cell["outputs"] = [
                {
                    "output_type": "error",
                    "ename": type(exc).__name__,
                    "evalue": str(exc),
                    "traceback": [line.rstrip("\n") for line in tb],
                }
            ]
            break
    except Exception:  # noqa: BLE001
        pass


_RUNNER_SOURCE = r'''
import json, sys, traceback
from pathlib import Path

in_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
timeout = int(sys.argv[3])
workdir = Path(sys.argv[4])

nb = json.loads(in_path.read_text(encoding="utf-8"))

def normalize(payload):
    payload = json.loads(json.dumps(payload))
    payload.setdefault("nbformat", 4)
    payload.setdefault("nbformat_minor", 5)
    payload.setdefault("metadata", {})
    cells = []
    for cell in payload.get("cells", []) or []:
        cell = dict(cell)
        src = cell.get("source", "")
        if isinstance(src, list):
            cell["source"] = "".join(str(x) for x in src)
        elif src is None:
            cell["source"] = ""
        else:
            cell["source"] = str(src)
        if cell.get("cell_type") == "code":
            cell.setdefault("outputs", [])
            cell.setdefault("execution_count", None)
        cell.setdefault("metadata", {})
        cells.append(cell)
    payload["cells"] = cells
    return payload

def dump(obj):
    return json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o)))

try:
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    nb = normalize(nb)
    notebook = nbformat.from_dict(nb)
    ks = (nb.get("metadata") or {}).get("kernelspec") or {}
    kernel_name = ks.get("name") or "python3"
    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name=kernel_name,
        resources={"metadata": {"path": str(workdir)}},
        allow_errors=True,
        store_widget_state=False,
    )
    try:
        client.execute()
    except CellExecutionError:
        pass
    except Exception as exc:
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            if cell.get("outputs"):
                continue
            cell["outputs"] = [{
                "output_type": "error",
                "ename": type(exc).__name__,
                "evalue": str(exc),
                "traceback": traceback.format_exc().splitlines(),
            }]
            break
    out_path.write_text(dump(notebook), encoding="utf-8")
except Exception as exc:
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            cell.setdefault("outputs", [])
            cell["outputs"].append({
                "output_type": "error",
                "ename": type(exc).__name__,
                "evalue": str(exc),
                "traceback": traceback.format_exc().splitlines(),
            })
            break
    out_path.write_text(json.dumps(nb), encoding="utf-8")
    sys.exit(0)
'''


def _execute_in_subprocess(
    notebook_bytes: bytes,
    *,
    timeout: int,
    workdir: Path,
) -> bytes:
    """
    Execute notebook in an isolated Python subprocess.

    The child writes the executed .ipynb to a temp path; the parent reads it back.
    """
    import subprocess
    import sys

    in_path = workdir / "input.ipynb"
    out_path = workdir / "output.ipynb"
    runner = workdir / "_j2p_exec_runner.py"
    in_path.write_bytes(notebook_bytes)
    runner.write_text(_RUNNER_SOURCE.strip() + "\n", encoding="utf-8")

    # Hard wall-clock limit slightly above per-cell timeout budget
    wall = max(timeout * 4, 120)
    proc = subprocess.run(
        [
            sys.executable,
            str(runner),
            str(in_path),
            str(out_path),
            str(timeout),
            str(workdir),
        ],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=wall,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    if not out_path.is_file():
        stderr = (proc.stderr or proc.stdout or "executor produced no output")[:2000]
        raise RuntimeError(f"Notebook execution failed: {stderr}")
    return out_path.read_bytes()


def execute_notebook(
    data: Union[bytes, str, Dict[str, Any]],
    filename: str = "notebook.ipynb",
    *,
    timeout: int = 60,
    use_cache: bool = True,
    use_subprocess: bool = True,
) -> ExecutionResult:
    """
    Execute a notebook when required, capturing all outputs.

    - Uses content-hash cache to skip redundant runs.
    - Continues after cell errors (allow_errors).
    - Prefers subprocess isolation away from the Streamlit process.
    """
    logs: List[str] = []
    try:
        nb = _load_nb(data)
        content_hash = notebook_content_hash(nb)
        logs.append(f"executor: hash={content_hash[:12]}...")

        if use_cache:
            cached = _cache_get(content_hash)
            if cached is not None:
                logs.append("executor: cache hit - reusing executed notebook")
                executed_n, failed_n = _count_code_failures(json.loads(cached.decode("utf-8")))
                return ExecutionResult(
                    success=True,
                    notebook_bytes=cached,
                    filename=filename,
                    executed=True,
                    from_cache=True,
                    cells_executed=executed_n,
                    cells_failed=failed_n,
                    logs=logs,
                    content_hash=content_hash,
                )

        raw_bytes = (
            data
            if isinstance(data, bytes)
            else json.dumps(nb).encode("utf-8")
        )

        workdir = Path(tempfile.mkdtemp(prefix="j2p_exec_"))
        try:
            logs.append(
                f"executor: running ({'subprocess' if use_subprocess else 'in-process'}) "
                f"timeout={timeout}s"
            )
            if use_subprocess:
                try:
                    out_bytes = _execute_in_subprocess(
                        raw_bytes, timeout=timeout, workdir=workdir
                    )
                except Exception as sub_exc:  # noqa: BLE001
                    logs.append(
                        f"executor: subprocess failed ({sub_exc}); falling back in-process"
                    )
                    executed_nb = _execute_with_nbclient(
                        nb, timeout=timeout, workdir=workdir
                    )
                    out_bytes = json.dumps(executed_nb).encode("utf-8")
            else:
                executed_nb = _execute_with_nbclient(
                    nb, timeout=timeout, workdir=workdir
                )
                out_bytes = json.dumps(executed_nb).encode("utf-8")

            out_nb = json.loads(out_bytes.decode("utf-8"))
            executed_n, failed_n = _count_code_failures(out_nb)
            if use_cache:
                _cache_put(content_hash, out_bytes)

            logs.append(
                f"executor: done | executed={executed_n} | failed={failed_n}"
            )
            return ExecutionResult(
                success=True,
                notebook_bytes=out_bytes,
                filename=filename,
                executed=True,
                from_cache=False,
                cells_executed=executed_n,
                cells_failed=failed_n,
                logs=logs,
                content_hash=content_hash,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Notebook execution failed for %s", filename)
        # Return original bytes so PDF can still be produced
        fallback = (
            data
            if isinstance(data, bytes)
            else json.dumps(_load_nb(data)).encode("utf-8")
        )
        return ExecutionResult(
            success=False,
            notebook_bytes=fallback,
            filename=filename,
            executed=False,
            error=str(exc),
            logs=logs + [f"executor: fatal error: {exc}"],
            content_hash=hashlib.sha256(fallback[:4096]).hexdigest(),
        )


def verify_execution(
    data: Union[bytes, str, Dict[str, Any]],
    filename: str = "notebook.ipynb",
) -> Dict[str, Any]:
    """Post-execution verification summary."""
    from .analyzer import analyze_notebook

    analysis = analyze_notebook(data, filename)
    return {
        "filename": filename,
        "verified": analysis.already_executed or analysis.code_cells == 0,
        "still_pending": analysis.unexecuted_code_cells,
        "error_cells": analysis.error_cells,
        "summary": analysis.summary,
    }
