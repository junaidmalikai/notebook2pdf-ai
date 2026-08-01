"""LangChain agent entrypoint - single LangGraph supervisor pipeline only."""

from __future__ import annotations

import queue
from datetime import datetime
from typing import Any, Dict, List

from services.graph.observability import configure_langsmith
from services.graph.workflow import run_conversion_graph, stream_conversion_graph
from utils.logging_config import get_logger
from utils.security import sanitize_error

logger = get_logger(__name__)
configure_langsmith()


def run_conversion_pipeline(
    *,
    notebooks: List[Dict[str, Any]],
    pdf_settings: Dict[str, Any],
    provider_id: str,
    api_key: str,
    model: str,
    use_llm_enrichment: bool = True,
    auto_execute: bool = True,
) -> Dict[str, Any]:
    """Sole conversion entry: AI-native LangGraph supervisor graph."""
    del use_llm_enrichment
    return dict(
        run_conversion_graph(
            notebooks=notebooks,  # type: ignore[arg-type]
            pdf_settings=pdf_settings,
            provider_id=provider_id,
            api_key=api_key,
            model=model,
            auto_execute=auto_execute,
        )
    )


def run_agent(
    query: str,
    notebooks: List[Dict[str, Any]],
    pdf_settings: Dict[str, Any],
    log_q: queue.Queue,
    result_box: dict,
    *,
    provider_id: str,
    api_key: str,
    model: str,
) -> None:
    """Stream the supervisor graph into the UI log. No secondary pipelines."""
    try:
        log_q.put(("info", f"AI supervisor started | {datetime.now().strftime('%H:%M:%S')}"))
        log_q.put(("info", f"provider -> {provider_id} | model -> {model}"))
        log_q.put(("info", f"files -> {len(notebooks)}"))
        log_q.put(("info", f"query -> {query}"))
        log_q.put(("info", "engine -> LangGraph supervisor + LangChain tool-calling agents"))

        for event in stream_conversion_graph(
            notebooks=notebooks,  # type: ignore[arg-type]
            pdf_settings=pdf_settings,
            provider_id=provider_id,
            api_key=api_key,
            model=model,
        ):
            for node_name, update in (event or {}).items():
                if not isinstance(update, dict):
                    continue
                for line in update.get("logs") or []:
                    log_q.put(("obs", f"{node_name}: {line}"))
                if update.get("next_agent"):
                    log_q.put(("tool", f"supervisor -> {update['next_agent']}"))
                if update.get("download_bytes") is not None:
                    result_box.update(
                        {
                            "download_bytes": update.get("download_bytes"),
                            "download_name": update.get("download_name"),
                            "download_mime": update.get("download_mime"),
                            "is_batch": update.get("is_batch", False),
                            "status": update.get("status"),
                            "error": update.get("error"),
                            "pdf_count": update.get("pdf_count")
                            or len(update.get("pdf_artifacts") or []),
                        }
                    )
                if update.get("status"):
                    result_box["status"] = update["status"]
                if update.get("error"):
                    result_box["error"] = update["error"]
                snap = update.get("agent_memory") or {}
                if snap.get("tool_trace"):
                    for tr in snap["tool_trace"][-3:]:
                        log_q.put(("tool", f"{tr.get('tool')} | {tr.get('detail')}"))

        if result_box.get("download_bytes") and result_box.get("status") == "ok":
            log_q.put(
                (
                    "ans",
                    f"complete -> {result_box.get('download_name')} "
                    f"({len(result_box['download_bytes']) // 1024} KB)",
                )
            )
        elif result_box.get("error"):
            log_q.put(("err", str(result_box["error"])))
        elif not result_box.get("download_bytes"):
            result_box["status"] = "error"
            result_box["error"] = result_box.get("error") or "Conversion finished without download"
            log_q.put(("err", result_box["error"]))

    except Exception as exc:  # noqa: BLE001
        logger.exception("Supervisor graph failed")
        log_q.put(("err", f"error: {sanitize_error(exc)}"))
        result_box["status"] = "error"
        result_box["error"] = sanitize_error(exc)
    finally:
        log_q.put(("__DONE__", ""))
