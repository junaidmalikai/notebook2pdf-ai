"""Session-bound LangChain StructuredTools for genuine AI tool calling.

Every tool here is invoked by LLM agents via create_react_agent / create_agent.
Tools close over AgentSession so the model does not invent file paths or bytes.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from services.agents.session import AgentSession
from utils.security import sanitize_error


class EmptyArgs(BaseModel):
    reason: str = Field(default="agent requested", description="Why this tool is called")


class FilenameArgs(BaseModel):
    filename: str = Field(description="Notebook filename from the uploaded session")
    reason: str = Field(default="agent requested")


class ExecutionDecisionArgs(BaseModel):
    filename: str = Field(description="Notebook filename from the uploaded session")
    needs_execution: bool = Field(
        description="AI decision: True if cells should be executed before PDF rendering"
    )
    rationale: str = Field(
        default="",
        description="Brief reasoning for the execution decision",
    )


class ExecuteArgs(BaseModel):
    filename: str = Field(description="Notebook filename to execute")
    reason: str = Field(default="unexecuted cells detected")


class MetadataWriteArgs(BaseModel):
    filename: str
    title: str = ""
    description: str = ""
    keywords: str = Field(default="", description="Comma-separated keywords")
    language: str = "python"


class DocWriteArgs(BaseModel):
    filename: str
    readme_markdown: str = Field(description="Full GitHub README markdown")
    executive_summary: str = ""
    insights: str = Field(default="", description="Semicolon-separated insights")
    features: str = Field(default="", description="Semicolon-separated features")
    architecture: str = ""
    code_explanation: str = ""
    dependencies: str = Field(default="", description="Comma-separated deps")


class MarkdownNotesArgs(BaseModel):
    filename: str
    notes: str = Field(description="Markdown quality notes / improvements advice")
    quality_score: int = Field(default=70, ge=0, le=100)


class CodeUnderstandingArgs(BaseModel):
    filename: str
    executive_summary: str
    key_techniques: str = Field(default="", description="Comma-separated techniques")
    libraries: str = Field(default="", description="Comma-separated libraries")
    data_flow: str = ""
    risks: str = Field(default="", description="Semicolon-separated risks")


class QualityWriteArgs(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    issues: str = Field(default="", description="Semicolon-separated issues")
    repair_agent: str = Field(
        default="",
        description="Agent name to repair, or empty if passed",
    )
    repair_instructions: str = ""
    summary: str = ""


class FinalApprovalArgs(BaseModel):
    approved: bool = Field(description="True if ready for PDF assembly / packaging")
    summary: str = Field(default="", description="Final approval rationale")


class ValidationWriteArgs(BaseModel):
    ok: bool
    ready_for_pdf: bool
    blocking_issues: str = Field(default="", description="Semicolon-separated")
    warnings: str = Field(default="", description="Semicolon-separated")


def _split(text: str, sep: str = ",") -> List[str]:
    return [p.strip() for p in (text or "").split(sep) if p.strip()]


def build_session_tools(session: AgentSession) -> Dict[str, List[StructuredTool]]:
    """Build role-grouped tools. Every returned tool is used by at least one agent."""

    def validate_api(reason: str = "validate credentials") -> str:
        from services.ai.factory import create_provider

        session.trace_tool("validate_api", reason)
        if not session.provider_id or not session.api_key:
            session.provider_ok = False
            session.error = "Please enter a valid API key to continue."
            return json.dumps({"ok": False, "message": session.error})
        try:
            provider = create_provider(
                session.provider_id, session.api_key, session.model or None
            )
            result = provider.validate(timeout=15.0)
            session.provider_ok = bool(result.ok)
            if not result.ok:
                session.error = result.message
            else:
                session.error = None
                session.status = "running"
            return json.dumps(
                {"ok": result.ok, "message": result.message, "models": result.models[:20]}
            )
        except Exception as exc:  # noqa: BLE001
            session.provider_ok = False
            session.error = sanitize_error(exc)
            return json.dumps({"ok": False, "message": session.error})

    def list_uploaded_notebooks(reason: str = "list uploads") -> str:
        session.trace_tool("list_uploaded_notebooks", reason)
        rows = [
            {"filename": n["filename"], "size": len(n["content"])} for n in session.notebooks
        ]
        return json.dumps({"ok": True, "count": len(rows), "notebooks": rows})

    def notebook_loader(filename: str, reason: str = "load") -> str:
        session.trace_tool("notebook_loader", f"{filename}|{reason}")
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
        except StopIteration:
            return json.dumps({"ok": False, "error": f"Unknown notebook {filename}"})
        return json.dumps(
            {"ok": True, "filename": filename, "size": len(raw), "message": "loaded"}
        )

    def notebook_parser(filename: str, reason: str = "parse") -> str:
        from services.notebook.parser import parse_notebook
        from services.pdf.engine import render_notebook_body, render_toc_html
        from models.pdf_settings import PDFSettings

        session.trace_tool("notebook_parser", f"{filename}|{reason}")
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            doc = parse_notebook(raw, filename)
            settings = PDFSettings.model_validate(session.pdf_settings or {})
            session.upsert_parsed(
                filename,
                {
                    "title": settings.resolved_title(doc.title),
                    "description": settings.resolved_description(doc.description),
                    "language": settings.resolved_language(doc.language),
                    "cell_count": len(doc.cells),
                    "code_cells": doc.code_cell_count,
                    "markdown_cells": doc.markdown_cell_count,
                    "cells_html": render_notebook_body(doc, settings),
                    "toc_html": render_toc_html(doc),
                    "source_title": doc.title,
                },
            )
            return json.dumps(
                {
                    "ok": True,
                    "filename": filename,
                    "title": settings.resolved_title(doc.title),
                    "description": settings.resolved_description(doc.description),
                    "language": settings.resolved_language(doc.language),
                    "cell_count": len(doc.cells),
                    "code_cells": doc.code_cell_count,
                    "markdown_cells": doc.markdown_cell_count,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": sanitize_error(exc)})

    def notebook_analyzer(filename: str, reason: str = "analyze") -> str:
        from services.notebook.analyzer import analyze_notebook

        session.trace_tool("notebook_analyzer", f"{filename}|{reason}")
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            analysis = analyze_notebook(raw, filename)
            payload = analysis.to_dict()
            # replace or append
            session.analyses = [a for a in session.analyses if a.get("filename") != filename]
            session.analyses.append(payload)
            return json.dumps({"ok": True, **payload})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": sanitize_error(exc)})

    def set_execution_decision(
        filename: str,
        needs_execution: bool,
        rationale: str = "",
    ) -> str:
        """Record the Analysis Agent's structured execution decision (no keyword parsing)."""
        session.trace_tool(
            "set_execution_decision",
            f"{filename}|needs={needs_execution}|{rationale}",
        )
        # Config kill-switch only: when auto_execute is disabled by environment/settings
        needs = bool(needs_execution) if session.auto_execute else False
        for a in session.analyses:
            if a.get("filename") == filename:
                a["needs_execution"] = needs
                a["ai_decision"] = rationale or (
                    "execute" if needs_execution else "skip execution"
                )
        session.needs_execution = any(a.get("needs_execution") for a in session.analyses)
        return json.dumps(
            {
                "ok": True,
                "filename": filename,
                "needs_execution": needs,
                "requested_needs_execution": bool(needs_execution),
                "auto_execute_enabled": session.auto_execute,
                "session_needs_execution": session.needs_execution,
                "rationale": rationale,
            }
        )

    def notebook_executor(filename: str, reason: str = "execute") -> str:
        from services.notebook.executor import execute_notebook, verify_execution

        session.trace_tool("notebook_executor", f"{filename}|{reason}")
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            result = execute_notebook(
                raw,
                filename,
                timeout=session.execution_timeout,
                use_cache=True,
                use_subprocess=True,
            )
            session.update_notebook_bytes(filename, result.notebook_bytes)
            verify = verify_execution(result.notebook_bytes, filename)
            report = {
                "filename": filename,
                "executed": result.executed,
                "from_cache": result.from_cache,
                "cells_executed": result.cells_executed,
                "cells_failed": result.cells_failed,
                "success": result.success,
                "error": result.error,
                "verified": bool(verify.get("verified")),
            }
            session.execution_reports = [
                r for r in session.execution_reports if r.get("filename") != filename
            ]
            session.execution_reports.append(report)
            for line in result.logs:
                session.log("notebook_executor", line)
            return json.dumps({"ok": result.success, **report, "logs": result.logs[-10:]})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": sanitize_error(exc)})

    def output_tool(filename: str, reason: str = "inventory outputs") -> str:
        session.trace_tool("output_tool", f"{filename}|{reason}")
        from services.langchain_tools.ai_tools import _output_inventory_tool

        return _output_inventory_tool(filename, session.notebook_b64(filename))

    def dependency_tool(filename: str, reason: str = "deps") -> str:
        session.trace_tool("dependency_tool", f"{filename}|{reason}")
        from services.langchain_tools.ai_tools import _dependency_tool

        return _dependency_tool(filename, session.notebook_b64(filename))

    def image_tool(filename: str, reason: str = "images") -> str:
        session.trace_tool("image_tool", f"{filename}|{reason}")
        from services.langchain_tools.ai_tools import _image_inventory_tool

        raw = _image_inventory_tool(filename, session.notebook_b64(filename))
        try:
            payload = json.loads(raw)
            session.upsert_parsed(filename, {"image_inventory": payload})
        except Exception:  # noqa: BLE001
            pass
        return raw

    def summary_tool(filename: str, reason: str = "summary") -> str:
        session.trace_tool("summary_tool", f"{filename}|{reason}")
        from services.langchain_tools.ai_tools import _summary_tool

        meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        return _summary_tool(
            filename,
            title=meta.get("title") or "",
            description=meta.get("description") or "",
            code_cells=int(meta.get("code_cells") or 0),
            markdown_cells=int(meta.get("markdown_cells") or 0),
        )

    def insights_tool(filename: str, reason: str = "insights") -> str:
        session.trace_tool("insights_tool", f"{filename}|{reason}")
        from services.langchain_tools.ai_tools import _insights_seed_tool
        from services.notebook.parser import parse_notebook

        meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        excerpt = meta.get("description") or ""
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            doc = parse_notebook(raw, filename)
            bits = [c.source[:500] for c in doc.visible_cells()[:8]]
            excerpt = "\n\n".join(bits)[:3500]
        except Exception:  # noqa: BLE001
            pass
        return _insights_seed_tool(filename, excerpt=excerpt, title=meta.get("title") or "")

    def markdown_renderer(filename: str, reason: str = "render md") -> str:
        from services.markdown.renderer import render_markdown_to_html
        from services.notebook.parser import parse_notebook

        session.trace_tool("markdown_renderer", f"{filename}|{reason}")
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            doc = parse_notebook(raw, filename)
            md = "\n\n".join(
                c.source for c in doc.visible_cells() if c.cell_type.value == "markdown"
            )
            html = render_markdown_to_html(md[:8000], default_language=doc.language)
            return json.dumps({"ok": True, "html_length": len(html), "markdown_chars": len(md)})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": sanitize_error(exc)})

    def write_markdown_notes(
        filename: str, notes: str, quality_score: int = 70
    ) -> str:
        session.trace_tool("write_markdown_notes", filename)
        session.upsert_parsed(
            filename, {"markdown_notes": notes, "markdown_score": quality_score}
        )
        return json.dumps({"ok": True, "filename": filename, "quality_score": quality_score})

    def write_code_understanding(
        filename: str,
        executive_summary: str,
        key_techniques: str = "",
        libraries: str = "",
        data_flow: str = "",
        risks: str = "",
    ) -> str:
        session.trace_tool("write_code_understanding", filename)
        understanding = {
            "executive_summary": executive_summary,
            "key_techniques": _split(key_techniques),
            "libraries": _split(libraries),
            "data_flow": data_flow,
            "risks": _split(risks, ";"),
        }
        session.upsert_parsed(
            filename,
            {
                "code_understanding": understanding,
                "executive_summary": executive_summary,
            },
        )
        return json.dumps({"ok": True, "filename": filename, "understanding": understanding})

    def metadata_tool(
        filename: str,
        title: str = "",
        description: str = "",
        keywords: str = "",
        language: str = "python",
    ) -> str:
        session.trace_tool("metadata_tool", filename)
        settings = session.pdf_settings or {}
        user_title = bool((settings.get("title") or "").strip())
        user_desc = bool((settings.get("description") or "").strip())
        patch: Dict[str, Any] = {"language": language or "python"}
        if title and not user_title:
            patch["title"] = title
        if description and not user_desc:
            patch["description"] = description
        if keywords:
            patch["keywords"] = _split(keywords)
        session.upsert_parsed(filename, patch)
        return json.dumps({"ok": True, "filename": filename, "applied": patch})

    def readme_tool(
        filename: str,
        readme_markdown: str,
        executive_summary: str = "",
        insights: str = "",
        features: str = "",
        architecture: str = "",
        code_explanation: str = "",
        dependencies: str = "",
    ) -> str:
        session.trace_tool("readme_tool", filename)
        insights_list = _split(insights, ";")
        features_list = _split(features, ";")
        deps_list = _split(dependencies)
        session.upsert_parsed(
            filename,
            {
                "readme_markdown": readme_markdown,
                "executive_summary": executive_summary
                or (session.parsed and next(
                    (p.get("executive_summary") for p in session.parsed if p.get("filename") == filename),
                    "",
                )),
                "insights": insights_list,
                "features": features_list,
                "architecture_notes": architecture,
                "code_explanation": code_explanation,
                "dependencies": deps_list,
            },
        )
        # Store standalone README for packaging
        session.readme_documents = [
            r for r in session.readme_documents if r.get("filename") != f"{filename}.README.md"
        ]
        stem = filename.rsplit(".", 1)[0]
        session.readme_documents.append(
            {"filename": f"{stem}_README.md", "content": readme_markdown}
        )
        doc_md = (
            f"# Documentation - {stem}\n\n"
            f"## Executive Summary\n\n{executive_summary}\n\n"
            f"## Architecture\n\n{architecture or 'See notebook structure.'}\n\n"
            f"## Code Explanation\n\n{code_explanation or 'See notebook cells.'}\n\n"
            f"## Dependencies\n\n"
            + ("\n".join(f"- `{d}`" for d in deps_list) or "- (see notebook imports)")
            + "\n\n## Insights\n\n"
            + ("\n".join(f"- {i}" for i in insights_list) or "- (none)")
            + "\n\n## Features\n\n"
            + ("\n".join(f"- {f}" for f in features_list) or "- (none)")
            + "\n"
        )
        session.readme_documents = [
            r for r in session.readme_documents if r.get("filename") != f"{stem}_DOCUMENTATION.md"
        ]
        session.readme_documents.append(
            {"filename": f"{stem}_DOCUMENTATION.md", "content": doc_md}
        )
        session.documentation_bundle[filename] = {
            "readme": readme_markdown,
            "documentation": doc_md,
            "executive_summary": executive_summary,
            "insights": insights_list,
            "features": features_list,
            "architecture": architecture,
            "code_explanation": code_explanation,
            "dependencies": deps_list,
        }
        return json.dumps(
            {
                "ok": True,
                "filename": filename,
                "readme_chars": len(readme_markdown),
                "packaged": [f"{stem}_README.md", f"{stem}_DOCUMENTATION.md"],
            }
        )

    def html_generator(filename: str, reason: str = "html") -> str:
        from models.pdf_settings import PDFSettings
        from services.pdf.engine import build_full_html

        session.trace_tool("html_generator", f"{filename}|{reason}")
        meta = next((p for p in session.parsed if p.get("filename") == filename), None)
        if not meta or not meta.get("cells_html"):
            # ensure parse first
            notebook_parser(filename, reason="auto-parse for html")
            meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        settings = PDFSettings.model_validate(session.pdf_settings or {})
        html = build_full_html(meta, settings)
        # keep one html per notebook order
        session.html_documents = [h for h in session.html_documents if not h.startswith(f"<!-- {filename} -->")]
        session.html_documents.append(f"<!-- {filename} -->\n{html}")
        return json.dumps({"ok": True, "filename": filename, "html_length": len(html)})

    def pdf_generator(filename: str, reason: str = "render pdf") -> str:
        from models.pdf_settings import PDFSettings
        from services.notebook.parser import parse_notebook
        from services.pdf.engine import generate_pdf

        session.trace_tool("pdf_generator", f"{filename}|{reason}")
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            meta = next((p for p in session.parsed if p.get("filename") == filename), {})
            settings = PDFSettings.model_validate(session.pdf_settings or {})
            settings = settings.model_copy(
                update={
                    "title": meta.get("title") or settings.title,
                    "description": meta.get("description") or settings.description,
                    "language": meta.get("language") or settings.language,
                }
            )
            doc = parse_notebook(raw, filename)
            pdf_bytes, _ = generate_pdf(doc, settings=settings)
            stem = filename.rsplit(".", 1)[0]
            art = {
                "filename": f"{stem}.pdf",
                "content": pdf_bytes,
                "title": meta.get("title") or stem,
            }
            session.pdf_artifacts = [
                a for a in session.pdf_artifacts if a.get("filename") != art["filename"]
            ]
            session.pdf_artifacts.append(art)
            return json.dumps(
                {
                    "ok": True,
                    "filename": art["filename"],
                    "size": len(pdf_bytes),
                    "title": art["title"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            session.error = sanitize_error(exc)
            return json.dumps({"ok": False, "error": session.error})

    def validation_tool(reason: str = "validate readiness") -> str:
        session.trace_tool("validation_tool", reason)
        from services.langchain_tools.ai_tools import _validation_tool

        parsed_lite = [
            {
                "filename": p.get("filename"),
                "title": p.get("title"),
                "cell_count": p.get("cell_count"),
                "cells_html": "yes" if p.get("cells_html") else "",
            }
            for p in session.parsed
        ]
        raw = _validation_tool(
            json.dumps(parsed_lite),
            analyses_json=json.dumps(session.analyses, default=str),
            execution_json=json.dumps(session.execution_reports, default=str),
        )
        return raw

    def write_validation(
        ok: bool,
        ready_for_pdf: bool,
        blocking_issues: str = "",
        warnings: str = "",
    ) -> str:
        session.trace_tool("write_validation", str(ok))
        session.validation = {
            "ok": ok,
            "ready_for_pdf": ready_for_pdf,
            "blocking_issues": _split(blocking_issues, ";"),
            "warnings": _split(warnings, ";"),
        }
        if session.validation["blocking_issues"]:
            session.error = "; ".join(session.validation["blocking_issues"])
            session.status = "error"
        return json.dumps({"ok": True, "validation": session.validation})

    def write_quality_review(
        score: int,
        passed: bool,
        issues: str = "",
        repair_agent: str = "",
        repair_instructions: str = "",
        summary: str = "",
    ) -> str:
        session.trace_tool("write_quality_review", f"score={score}")
        session.quality = {
            "score": score,
            "passed": passed,
            "issues": _split(issues, ";"),
            "repair_agent": repair_agent or None,
            "repair_instructions": repair_instructions,
            "summary": summary,
        }
        if not passed and repair_agent:
            session.repair_loops += 1
        return json.dumps({"ok": True, "quality": session.quality})

    def write_final_approval(approved: bool, summary: str = "") -> str:
        """AI final approval gate before PDF assembly / packaging proceeds."""
        session.trace_tool("write_final_approval", f"approved={approved}")
        session.quality = {
            **(session.quality or {}),
            "final_approved": bool(approved),
            "final_approval_summary": summary,
        }
        if not approved and not (session.quality or {}).get("repair_agent"):
            session.quality["repair_agent"] = "coordinator"
            session.quality["passed"] = False
        elif approved:
            session.quality["passed"] = True
            session.quality["repair_agent"] = None
        return json.dumps({"ok": True, "approved": approved, "summary": summary})

    def packaging_tool(reason: str = "package download") -> str:
        session.trace_tool("packaging_tool", reason)
        if not session.pdf_artifacts:
            return json.dumps({"ok": False, "error": "No PDF artifacts to package"})
        try:
            # Single notebook: download the PDF directly (no ZIP).
            if len(session.pdf_artifacts) == 1:
                art = session.pdf_artifacts[0]
                session.download_bytes = art["content"]
                session.download_name = art["filename"]
                session.download_mime = "application/pdf"
                session.is_batch = False
                session.pdf_count = 1
                session.status = "ok"
                session.error = None
                return json.dumps(
                    {
                        "ok": True,
                        "download_name": session.download_name,
                        "mime": session.download_mime,
                        "size": len(session.download_bytes),
                        "pdf_count": 1,
                    }
                )

            # Multiple notebooks: ZIP of all PDFs (existing behavior).
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for art in session.pdf_artifacts:
                    zf.writestr(art["filename"], art["content"])
                for doc in session.readme_documents:
                    zf.writestr(doc["filename"], doc["content"].encode("utf-8"))
                index = {
                    "pdfs": [a["filename"] for a in session.pdf_artifacts],
                    "docs": [d["filename"] for d in session.readme_documents],
                    "quality": session.quality,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                }
                zf.writestr("conversion_manifest.json", json.dumps(index, indent=2))
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session.download_bytes = buf.getvalue()
            session.download_name = f"notebooks_pdf_{stamp}.zip"
            session.download_mime = "application/zip"
            session.is_batch = True
            session.pdf_count = len(session.pdf_artifacts)
            session.status = "ok"
            session.error = None
            return json.dumps(
                {
                    "ok": True,
                    "download_name": session.download_name,
                    "mime": session.download_mime,
                    "size": len(session.download_bytes),
                    "pdf_count": session.pdf_count,
                    "doc_count": len(session.readme_documents),
                }
            )
        except Exception as exc:  # noqa: BLE001
            session.error = sanitize_error(exc)
            session.status = "error"
            return json.dumps({"ok": False, "error": session.error})

    def download_tool(reason: str = "confirm download") -> str:
        session.trace_tool("download_tool", reason)
        if not session.download_bytes:
            return json.dumps({"ok": False, "error": "No download payload"})
        return json.dumps(
            {
                "ok": True,
                "download_name": session.download_name,
                "size": len(session.download_bytes),
                "mime": session.download_mime,
                "is_batch": session.is_batch,
            }
        )

    def lcel_metadata_enrichment(filename: str, reason: str = "LCEL metadata") -> str:
        """Run LCEL metadata enrichment chain and apply results via metadata_tool semantics."""
        from services.agents.llm import get_llm
        from services.graph.chains import build_metadata_enrichment_chain, invoke_chain_to_dict

        session.trace_tool("lcel_metadata_enrichment", f"{filename}|{reason}")
        meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        llm = get_llm(session.provider_id, session.api_key, session.model)
        chain = build_metadata_enrichment_chain(llm)
        result = invoke_chain_to_dict(
            chain,
            {
                "filename": filename,
                "title": meta.get("title") or filename,
                "description": meta.get("description") or "",
                "language": meta.get("language") or "python",
                "code_understanding": str(meta.get("code_understanding") or "")[:2000],
            },
        )
        return metadata_tool(
            filename,
            title=result.get("title") or "",
            description=result.get("description") or "",
            keywords=",".join(result.get("keywords") or []),
            language=result.get("language") or meta.get("language") or "python",
        )

    def lcel_code_insights(filename: str, reason: str = "LCEL insights") -> str:
        from services.agents.llm import get_llm
        from services.graph.chains import build_insights_chain, invoke_chain_to_dict

        session.trace_tool("lcel_code_insights", f"{filename}|{reason}")
        seed = json.loads(insights_tool(filename, reason="seed"))
        meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        llm = get_llm(session.provider_id, session.api_key, session.model)
        result = invoke_chain_to_dict(
            build_insights_chain(llm),
            {
                "filename": filename,
                "title": meta.get("title") or "",
                "description": meta.get("description") or "",
                "language": meta.get("language") or "python",
                "excerpt": seed.get("excerpt") or "",
            },
        )
        return write_code_understanding(
            filename,
            executive_summary=result.get("executive_summary") or "",
            key_techniques=",".join(result.get("key_techniques") or []),
            libraries=",".join(result.get("libraries") or []),
            data_flow=result.get("data_flow") or "",
            risks=";".join(result.get("risks") or []),
        )

    def lcel_readme_generation(filename: str, reason: str = "LCEL readme") -> str:
        from services.agents.llm import get_llm
        from services.graph.chains import build_readme_chain, invoke_chain_to_dict

        session.trace_tool("lcel_readme_generation", f"{filename}|{reason}")
        meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        llm = get_llm(session.provider_id, session.api_key, session.model)
        result = invoke_chain_to_dict(
            build_readme_chain(llm),
            {
                "filename": filename,
                "title": meta.get("title") or filename,
                "description": meta.get("description") or "",
                "language": meta.get("language") or "python",
                "keywords": ",".join(meta.get("keywords") or []),
                "code_understanding": str(meta.get("code_understanding") or "")[:2500],
                "insights": ",".join(meta.get("insights") or []),
            },
        )
        return readme_tool(
            filename,
            readme_markdown=result.get("readme_markdown") or result.get("raw") or "",
            executive_summary=result.get("executive_summary") or "",
            insights=";".join(result.get("insights") or []),
            features=";".join(result.get("features") or []),
            architecture="See README Architecture section.",
            code_explanation=str((meta.get("code_understanding") or {}).get("executive_summary") or ""),
            dependencies=",".join(meta.get("dependencies") or []),
        )

    def lcel_markdown_review(filename: str, reason: str = "LCEL markdown") -> str:
        from services.agents.llm import get_llm
        from services.graph.chains import build_markdown_review_chain, invoke_chain_to_dict
        from services.notebook.parser import parse_notebook

        session.trace_tool("lcel_markdown_review", f"{filename}|{reason}")
        excerpt = ""
        try:
            raw = next(n["content"] for n in session.notebooks if n["filename"] == filename)
            doc = parse_notebook(raw, filename)
            excerpt = "\n\n".join(
                c.source[:600]
                for c in doc.visible_cells()
                if c.cell_type.value == "markdown"
            )[:3500]
        except Exception:  # noqa: BLE001
            excerpt = ""
        llm = get_llm(session.provider_id, session.api_key, session.model)
        result = invoke_chain_to_dict(
            build_markdown_review_chain(llm),
            {"filename": filename, "excerpt": excerpt or "(empty)"},
        )
        return write_markdown_notes(
            filename,
            notes=result.get("notes") or "",
            quality_score=int(result.get("quality_score") or 70),
        )

    def lcel_quality_review(reason: str = "LCEL quality") -> str:
        from services.agents.llm import get_llm
        from services.graph.chains import (
            build_context_assign,
            build_quality_review_chain,
            build_status_branch,
            identity_passthrough,
            invoke_chain_to_dict,
        )
        from langchain_core.runnables import RunnableLambda

        session.trace_tool("lcel_quality_review", reason)
        llm = get_llm(session.provider_id, session.api_key, session.model)
        summary = [
            {
                "filename": p.get("filename"),
                "title": p.get("title"),
                "has_readme": bool(p.get("readme_markdown")),
                "has_summary": bool(p.get("executive_summary")),
                "images": (p.get("image_inventory") or {}).get("image_count"),
            }
            for p in session.parsed
        ]
        payload = {
            "ok": True,
            "threshold": session.quality_threshold,
            "parsed_summary": json.dumps(summary)[:5000],
            "validation": json.dumps(session.validation),
            "execution": json.dumps(session.execution_reports, default=str)[:2000],
            "prior_quality": json.dumps(session.quality),
        }
        # Live LCEL: Passthrough | Assign | Branch | quality chain
        branch = build_status_branch(
            identity_passthrough() | build_context_assign() | build_quality_review_chain(llm),
            RunnableLambda(lambda x: {"score": 0, "passed": False, "issues": ["branch_error"], "summary": "ok=false"}),
        )
        result = invoke_chain_to_dict(branch, payload)
        return write_quality_review(
            score=int(result.get("score") or 0),
            passed=bool(result.get("passed")),
            issues=";".join(result.get("issues") or []),
            repair_agent=result.get("repair_agent") or "",
            repair_instructions=result.get("repair_instructions") or "",
            summary=result.get("summary") or "",
        )

    def lcel_parallel_enrichment(filename: str, reason: str = "LCEL parallel") -> str:
        from services.agents.llm import get_llm
        from services.graph.chains import build_parallel_enrichment, invoke_chain_to_dict

        session.trace_tool("lcel_parallel_enrichment", f"{filename}|{reason}")
        meta = next((p for p in session.parsed if p.get("filename") == filename), {})
        seed = json.loads(insights_tool(filename, reason="seed"))
        llm = get_llm(session.provider_id, session.api_key, session.model)
        result = invoke_chain_to_dict(
            build_parallel_enrichment(llm),
            {
                "filename": filename,
                "title": meta.get("title") or filename,
                "description": meta.get("description") or "",
                "language": meta.get("language") or "python",
                "code_understanding": str(meta.get("code_understanding") or ""),
                "excerpt": seed.get("excerpt") or meta.get("description") or "",
            },
        )
        # Apply branch outputs
        md = result.get("metadata") or {}
        if hasattr(md, "model_dump"):
            md = md.model_dump()
        ins = result.get("insights") or {}
        if hasattr(ins, "model_dump"):
            ins = ins.model_dump()
        mrev = result.get("markdown") or {}
        if hasattr(mrev, "model_dump"):
            mrev = mrev.model_dump()
        if md:
            metadata_tool(
                filename,
                title=md.get("title") or "",
                description=md.get("description") or "",
                keywords=",".join(md.get("keywords") or []),
            )
        if ins:
            write_code_understanding(
                filename,
                executive_summary=ins.get("executive_summary") or "",
                key_techniques=",".join(ins.get("key_techniques") or []),
                libraries=",".join(ins.get("libraries") or []),
                data_flow=ins.get("data_flow") or "",
                risks=";".join(ins.get("risks") or []),
            )
        if mrev:
            write_markdown_notes(
                filename,
                notes=mrev.get("notes") or "",
                quality_score=int(mrev.get("quality_score") or 70),
            )
        return json.dumps({"ok": True, "branches": list(result.keys())})

    def get_session_snapshot(reason: str = "inspect state") -> str:
        session.trace_tool("get_session_snapshot", reason)
        return json.dumps(
            {
                "notebooks": [n["filename"] for n in session.notebooks],
                "needs_execution": session.needs_execution,
                "analyses": session.analyses,
                "execution_reports": session.execution_reports,
                "parsed": [
                    {
                        "filename": p.get("filename"),
                        "title": p.get("title"),
                        "has_readme": bool(p.get("readme_markdown")),
                        "has_summary": bool(p.get("executive_summary")),
                        "keywords": p.get("keywords") or [],
                        "images": (p.get("image_inventory") or {}).get("image_count"),
                        "markdown_score": p.get("markdown_score"),
                    }
                    for p in session.parsed
                ],
                "pdf_artifacts": [a.get("filename") for a in session.pdf_artifacts],
                "readme_documents": [d.get("filename") for d in session.readme_documents],
                "validation": session.validation,
                "quality": session.quality,
                "repair_loops": session.repair_loops,
                "status": session.status,
                "error": session.error,
                "has_download": bool(session.download_bytes),
            },
            default=str,
        )[:12000]

    # --- Assemble role toolkits (every tool assigned to >=1 agent) ---
    catalog: Dict[str, StructuredTool] = {
        "validate_api": StructuredTool.from_function(
            func=validate_api, name="validate_api", description="Validate provider API key.",
            args_schema=EmptyArgs,
        ),
        "list_uploaded_notebooks": StructuredTool.from_function(
            func=list_uploaded_notebooks, name="list_uploaded_notebooks",
            description="List notebooks in the current upload session.",
            args_schema=EmptyArgs,
        ),
        "notebook_loader": StructuredTool.from_function(
            func=notebook_loader, name="notebook_loader",
            description="Confirm a notebook is loaded in session.",
            args_schema=FilenameArgs,
        ),
        "notebook_parser": StructuredTool.from_function(
            func=notebook_parser, name="notebook_parser",
            description="Parse notebook structure and prepare HTML body fragments.",
            args_schema=FilenameArgs,
        ),
        "notebook_analyzer": StructuredTool.from_function(
            func=notebook_analyzer, name="notebook_analyzer",
            description="Analyze cell execution status (unexecuted/errors/outputs).",
            args_schema=FilenameArgs,
        ),
        "set_execution_decision": StructuredTool.from_function(
            func=set_execution_decision, name="set_execution_decision",
            description=(
                "Record the AI execution decision with an explicit needs_execution boolean "
                "and rationale. Do not encode the decision in free-text keywords."
            ),
            args_schema=ExecutionDecisionArgs,
        ),
        "notebook_executor": StructuredTool.from_function(
            func=notebook_executor, name="notebook_executor",
            description="Execute notebook cells via nbclient (captures outputs/images/errors).",
            args_schema=ExecuteArgs,
        ),
        "output_tool": StructuredTool.from_function(
            func=output_tool, name="output_tool",
            description="Inventory stdout/stderr/errors/images/tables in outputs.",
            args_schema=FilenameArgs,
        ),
        "dependency_tool": StructuredTool.from_function(
            func=dependency_tool, name="dependency_tool",
            description="Extract import/dependency hints from code cells.",
            args_schema=FilenameArgs,
        ),
        "image_tool": StructuredTool.from_function(
            func=image_tool, name="image_tool",
            description="Inventory image outputs and missing payloads.",
            args_schema=FilenameArgs,
        ),
        "summary_tool": StructuredTool.from_function(
            func=summary_tool, name="summary_tool",
            description="Structural notebook summary for reasoning.",
            args_schema=FilenameArgs,
        ),
        "insights_tool": StructuredTool.from_function(
            func=insights_tool, name="insights_tool",
            description="Prepare excerpt context for documentation insights.",
            args_schema=FilenameArgs,
        ),
        "markdown_renderer": StructuredTool.from_function(
            func=markdown_renderer, name="markdown_renderer",
            description="Render notebook markdown to HTML for quality inspection.",
            args_schema=FilenameArgs,
        ),
        "write_markdown_notes": StructuredTool.from_function(
            func=write_markdown_notes, name="write_markdown_notes",
            description="Store markdown quality notes after reviewing content.",
            args_schema=MarkdownNotesArgs,
        ),
        "write_code_understanding": StructuredTool.from_function(
            func=write_code_understanding, name="write_code_understanding",
            description="Store code understanding analysis for a notebook.",
            args_schema=CodeUnderstandingArgs,
        ),
        "metadata_tool": StructuredTool.from_function(
            func=metadata_tool, name="metadata_tool",
            description="Write title/description/keywords (respects user PDF settings).",
            args_schema=MetadataWriteArgs,
        ),
        "readme_tool": StructuredTool.from_function(
            func=readme_tool, name="readme_tool",
            description=(
                "Write GitHub README + documentation bundle (architecture, insights, deps) "
                "and stage files for ZIP packaging."
            ),
            args_schema=DocWriteArgs,
        ),
        "html_generator": StructuredTool.from_function(
            func=html_generator, name="html_generator",
            description="Build full HTML document (same layout source as PDF).",
            args_schema=FilenameArgs,
        ),
        "pdf_generator": StructuredTool.from_function(
            func=pdf_generator, name="pdf_generator",
            description="Render professional PDF via WeasyPrint (appearance unchanged).",
            args_schema=FilenameArgs,
        ),
        "validation_tool": StructuredTool.from_function(
            func=validation_tool, name="validation_tool",
            description="Run structural validation against parsed/execution state.",
            args_schema=EmptyArgs,
        ),
        "write_validation": StructuredTool.from_function(
            func=write_validation, name="write_validation",
            description="Persist AI validation judgment after reviewing validation_tool output.",
            args_schema=ValidationWriteArgs,
        ),
        "write_quality_review": StructuredTool.from_function(
            func=write_quality_review, name="write_quality_review",
            description="Persist quality score and optional repair_agent delegation.",
            args_schema=QualityWriteArgs,
        ),
        "write_final_approval": StructuredTool.from_function(
            func=write_final_approval, name="write_final_approval",
            description=(
                "Record AI final approval before PDF assembly. "
                "approved=true means proceed; false triggers repair via supervisor."
            ),
            args_schema=FinalApprovalArgs,
        ),
        "packaging_tool": StructuredTool.from_function(
            func=packaging_tool, name="packaging_tool",
            description=(
                "Package download payload: single PDF when one notebook; "
                "ZIP of PDFs when multiple notebooks."
            ),
            args_schema=EmptyArgs,
        ),
        "download_tool": StructuredTool.from_function(
            func=download_tool, name="download_tool",
            description="Confirm download payload readiness for the UI.",
            args_schema=EmptyArgs,
        ),
        "get_session_snapshot": StructuredTool.from_function(
            func=get_session_snapshot, name="get_session_snapshot",
            description="Inspect current conversion session state for reasoning.",
            args_schema=EmptyArgs,
        ),
        "lcel_metadata_enrichment": StructuredTool.from_function(
            func=lcel_metadata_enrichment, name="lcel_metadata_enrichment",
            description="Run LCEL RunnableSequence metadata enrichment and apply results.",
            args_schema=FilenameArgs,
        ),
        "lcel_code_insights": StructuredTool.from_function(
            func=lcel_code_insights, name="lcel_code_insights",
            description="Run LCEL code-understanding chain and store results.",
            args_schema=FilenameArgs,
        ),
        "lcel_readme_generation": StructuredTool.from_function(
            func=lcel_readme_generation, name="lcel_readme_generation",
            description="Run LCEL README/documentation chain and package docs.",
            args_schema=FilenameArgs,
        ),
        "lcel_markdown_review": StructuredTool.from_function(
            func=lcel_markdown_review, name="lcel_markdown_review",
            description="Run LCEL markdown review chain and store notes.",
            args_schema=FilenameArgs,
        ),
        "lcel_quality_review": StructuredTool.from_function(
            func=lcel_quality_review, name="lcel_quality_review",
            description="Run LCEL quality review chain and persist score/repair.",
            args_schema=EmptyArgs,
        ),
        "lcel_parallel_enrichment": StructuredTool.from_function(
            func=lcel_parallel_enrichment, name="lcel_parallel_enrichment",
            description="Run LCEL RunnableParallel (metadata+insights+markdown) for one notebook.",
            args_schema=FilenameArgs,
        ),
    }

    roles: Dict[str, List[str]] = {
        "validation_bootstrap": ["validate_api", "list_uploaded_notebooks", "get_session_snapshot"],
        "notebook_analysis": [
            "list_uploaded_notebooks",
            "notebook_loader",
            "notebook_analyzer",
            "output_tool",
            "set_execution_decision",
            "get_session_snapshot",
        ],
        "notebook_execution": [
            "get_session_snapshot",
            "notebook_executor",
            "output_tool",
        ],
        "code_understanding": [
            "notebook_parser",
            "dependency_tool",
            "insights_tool",
            "summary_tool",
            "lcel_code_insights",
            "write_code_understanding",
            "get_session_snapshot",
        ],
        "markdown": [
            "markdown_renderer",
            "insights_tool",
            "lcel_markdown_review",
            "write_markdown_notes",
            "get_session_snapshot",
        ],
        "metadata": [
            "notebook_parser",
            "summary_tool",
            "lcel_metadata_enrichment",
            "metadata_tool",
            "get_session_snapshot",
        ],
        "documentation": [
            "insights_tool",
            "dependency_tool",
            "summary_tool",
            "lcel_readme_generation",
            "readme_tool",
            "get_session_snapshot",
        ],
        "image_processing": ["image_tool", "output_tool", "get_session_snapshot"],
        "coordinator": [
            "get_session_snapshot",
            "metadata_tool",
            "summary_tool",
            "lcel_parallel_enrichment",
        ],
        "validation": [
            "validation_tool",
            "write_validation",
            "get_session_snapshot",
        ],
        "quality_review": [
            "get_session_snapshot",
            "html_generator",
            "markdown_renderer",
            "image_tool",
            "lcel_quality_review",
            "write_quality_review",
            "write_final_approval",
        ],
        "pdf_assembly": [
            "notebook_parser",
            "html_generator",
            "pdf_generator",
            "get_session_snapshot",
        ],
        "packaging": ["packaging_tool", "download_tool", "get_session_snapshot"],
    }

    return {role: [catalog[n] for n in names] for role, names in roles.items()}


def all_registered_tool_names(toolkits: Dict[str, List[StructuredTool]]) -> List[str]:
    names = set()
    for tools in toolkits.values():
        for t in tools:
            names.add(t.name)
    return sorted(names)
