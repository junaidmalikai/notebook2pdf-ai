"""
Notebook2PDF AI — Streamlit UI

AI-native LangGraph orchestration for Jupyter notebook → PDF conversion.

Run:  streamlit run app.py
"""

from __future__ import annotations

import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from config.settings import settings
from services.agent import run_agent, run_conversion_pipeline
from ui.pdf_settings_panel import render_pdf_settings_panel
from ui.sidebar import get_connection, render_ai_sidebar
from ui.styles import inject_css
from utils.logging_config import get_logger, setup_logging

setup_logging(settings.log_level)
logger = get_logger(__name__)

st.set_page_config(
    page_title="Notebook2PDF AI",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="expanded",
)

SAMPLE_PDF_PATH = ROOT / "samples" / "LangChain_Tool_Docstrings.pdf"

inject_css()

_STATE_DEFAULTS = {
    "notebooks": [],  # list[{filename, content}]
    "download_bytes": None,
    "download_name": None,
    "download_mime": None,
    "is_batch": False,
    "log": [],
    "status": None,
    "msg": "",
    "pdf_count": 0,
}
for key, value in _STATE_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def _render_log(lines) -> str:
    cls_map = {
        "tool": "l-tool",
        "obs": "l-obs",
        "err": "l-err",
        "info": "l-info",
        "ans": "l-ans",
    }
    rows = ""
    ts = datetime.now().strftime("%H:%M:%S")
    for kind, msg in lines:
        safe = str(msg).replace("<", "&lt;").replace(">", "&gt;")
        rows += (
            f'<div><span class="l-ts">{ts}</span>'
            f'<span class="{cls_map.get(kind, "l-info")}">{safe}</span></div>'
        )
    return f'<div class="terminal">{rows}</div>'


def _clear_outputs() -> None:
    st.session_state.download_bytes = None
    st.session_state.download_name = None
    st.session_state.download_mime = None
    st.session_state.is_batch = False
    st.session_state.log = []
    st.session_state.status = None
    st.session_state.msg = ""
    st.session_state.pdf_count = 0


# ── Sidebar ──────────────────────────────────────────────────────────────────
ai_ready = render_ai_sidebar()
connection = get_connection()

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero ani">
  <div class="hero-eyebrow">AI-Native LangGraph Orchestration with Deterministic Tools</div>
  <div class="hero-name">Notebook2PDF<br/><em>AI</em></div>
  <div class="hero-rule"></div>
  <div class="hero-desc">Notebook2PDF AI is an AI-native multi-agent platform that converts Jupyter notebooks into professional, publication-ready PDF documents using LangGraph orchestration and LangChain tools.</div>
  <div class="hero-desc">AI agents intelligently analyze, validate, enrich, and coordinate the conversion workflow, while deterministic tools ensure accurate notebook execution and high-quality PDF rendering.</div>
</div>
<div class="steps ani">
  <div class="step"><div class="step-n">1</div><div class="step-t">Paste<br/>API Key</div></div>
  <div class="step"><div class="step-n">2</div><div class="step-t">PDF<br/>Settings</div></div>
  <div class="step"><div class="step-n">3</div><div class="step-t">Upload<br/>.ipynb</div></div>
  <div class="step"><div class="step-n">4</div><div class="step-t">Download<br/>PDF / ZIP</div></div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Sample PDF ───────────────────────────────────────────────────────────────
st.markdown('<div class="pane ani">', unsafe_allow_html=True)
st.markdown('<div class="pane-lbl">📄 Sample PDF</div>', unsafe_allow_html=True)
st.caption("Preview a professional PDF produced by Notebook2PDF AI.")
if SAMPLE_PDF_PATH.is_file():
    st.download_button(
        label="Download Sample PDF",
        data=SAMPLE_PDF_PATH.read_bytes(),
        file_name="LangChain_Tool_Docstrings.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="sample_pdf_download",
    )
else:
    st.info("Sample PDF is not available in this checkout.")
st.markdown("</div>", unsafe_allow_html=True)

if not ai_ready:
    st.markdown(
        """
        <div class="r-box r-warn ani">
          <div class="r-ttl">Application Locked</div>
          <div class="r-bod">Please enter a valid API key to continue.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── PDF Settings ─────────────────────────────────────────────────────────────
pdf_settings = render_pdf_settings_panel(disabled=not ai_ready)

# ── Upload ───────────────────────────────────────────────────────────────────
st.markdown('<div class="pane ani">', unsafe_allow_html=True)
st.markdown('<div class="pane-lbl">Upload Notebooks</div>', unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Drop one or more .ipynb files here",
    type=["ipynb"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    disabled=not ai_ready,
)

if uploaded_files and ai_ready:
    notebooks = []
    max_bytes = settings.max_upload_mb * 1024 * 1024
    for uf in uploaded_files:
        raw = uf.read()
        if len(raw) > max_bytes:
            st.error(f"{uf.name} exceeds {settings.max_upload_mb} MB limit.")
            continue
        notebooks.append({"filename": uf.name, "content": raw})
    # Detect change
    prev = st.session_state.notebooks or []
    prev_sig = [(n["filename"], len(n["content"])) for n in prev]
    new_sig = [(n["filename"], len(n["content"])) for n in notebooks]
    if new_sig != prev_sig:
        st.session_state.notebooks = notebooks
        _clear_outputs()

if st.session_state.notebooks:
    for nb in st.session_state.notebooks:
        st.markdown(
            f"""
            <div class="fbadge">
              <span>NB</span>
              <strong>{nb['filename']}</strong>
              <span style="color:rgba(237,229,207,.3)">|</span>
              <span>{len(nb['content']) // 1024} KB</span>
              <span style="margin-left:auto;color:#3aad6e;">ready</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    n = len(st.session_state.notebooks)
    st.caption(
        f"{n} notebook(s) | "
        + ("single PDF download" if n == 1 else "batch ZIP download")
    )

go = st.button(
    "Generate PDF" if len(st.session_state.notebooks or []) <= 1 else "Generate PDFs (ZIP)",
    use_container_width=True,
    disabled=not ai_ready or not st.session_state.notebooks,
)
st.markdown("</div>", unsafe_allow_html=True)


def _run_conversion(*, use_agent: bool = True) -> None:
    if not st.session_state.notebooks:
        st.error("Please upload at least one .ipynb notebook.")
        return
    if not connection:
        st.error("Please enter a valid API key to continue.")
        return

    _clear_outputs()
    notebooks_snap = [
        {"filename": n["filename"], "content": bytes(n["content"])}
        for n in st.session_state.notebooks
    ]
    settings_snap = pdf_settings.model_dump()
    result_box: dict = {}

    st.markdown('<div class="pane ani">', unsafe_allow_html=True)
    st.markdown('<div class="pane-lbl">LangGraph Pipeline Log</div>', unsafe_allow_html=True)
    ph = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

    if use_agent:
        query = (
            f"Convert {len(notebooks_snap)} uploaded notebook(s) to professional PDF(s) "
            "using the LangGraph conversion pipeline."
        )
        log_q: queue.Queue = queue.Queue()
        thread = threading.Thread(
            target=run_agent,
            args=(query, notebooks_snap, settings_snap, log_q, result_box),
            kwargs={
                "provider_id": connection["provider_id"],
                "api_key": connection["api_key"],
                "model": connection["model"],
            },
            daemon=True,
        )
        thread.start()
        while thread.is_alive() or not log_q.empty():
            try:
                kind, msg = log_q.get(timeout=0.2)
                if kind == "__DONE__":
                    break
                st.session_state.log.append((kind, msg))
                ph.markdown(_render_log(st.session_state.log), unsafe_allow_html=True)
            except queue.Empty:
                continue
        thread.join(timeout=20)
        ph.markdown(_render_log(st.session_state.log), unsafe_allow_html=True)
    else:
        st.session_state.log.append(("info", "LangGraph pipeline started"))
        ph.markdown(_render_log(st.session_state.log), unsafe_allow_html=True)
        final = run_conversion_pipeline(
            notebooks=notebooks_snap,
            pdf_settings=settings_snap,
            provider_id=connection["provider_id"],
            api_key=connection["api_key"],
            model=connection["model"],
        )
        result_box.update(final)
        for line in final.get("logs") or []:
            st.session_state.log.append(("obs", line))
        if final.get("error"):
            st.session_state.log.append(("err", final["error"]))
        ph.markdown(_render_log(st.session_state.log), unsafe_allow_html=True)

    if result_box.get("download_bytes") and result_box.get("status") == "ok":
        st.session_state.download_bytes = result_box["download_bytes"]
        st.session_state.download_name = result_box.get("download_name") or "notebook.pdf"
        st.session_state.download_mime = result_box.get("download_mime") or "application/pdf"
        st.session_state.is_batch = bool(result_box.get("is_batch"))
        st.session_state.pdf_count = int(result_box.get("pdf_count") or (2 if st.session_state.is_batch else 1))
        st.session_state.status = "ok"
        st.session_state.msg = (
            f"{st.session_state.download_name} | "
            f"{len(st.session_state.download_bytes) // 1024} KB"
        )
    else:
        st.session_state.status = "err"
        st.session_state.msg = (
            result_box.get("error")
            or next(
                (m for k, m in reversed(st.session_state.log) if k == "err"),
                "Conversion failed.",
            )
        )
    st.rerun()


if go:
    _run_conversion(use_agent=True)

if st.session_state.log and not go:
    st.markdown('<div class="pane ani">', unsafe_allow_html=True)
    st.markdown('<div class="pane-lbl">LangGraph Pipeline Log</div>', unsafe_allow_html=True)
    st.markdown(_render_log(st.session_state.log), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.status == "ok" and st.session_state.download_bytes:
    label = "Download ZIP" if st.session_state.is_batch else "Download PDF"
    st.markdown(
        f"""
        <div class="r-box r-ok ani">
          <div class="r-ttl">Ready</div>
          <div class="r-bod">{st.session_state.msg}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        label,
        data=st.session_state.download_bytes,
        file_name=st.session_state.download_name or "notebook.pdf",
        mime=st.session_state.download_mime or "application/pdf",
        use_container_width=True,
        disabled=not ai_ready,
    )
elif st.session_state.status == "err":
    st.markdown(
        f"""
        <div class="r-box r-err ani">
          <div class="r-ttl">Conversion Failed</div>
          <div class="r-bod">{st.session_state.msg}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="pgfoot">
      Notebook2PDF AI · Muhammad Junaid · junaidfazal08@gmail.com · 0304-1659294 · Streamlit Cloud Ready
    </div>
    </div>
    """,
    unsafe_allow_html=True,
)
