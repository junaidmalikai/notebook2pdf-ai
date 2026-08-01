"""Enterprise PDF generation engine for Jupyter notebooks (PDFSettings-driven)."""

from __future__ import annotations

import base64
import html
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

from models.pdf_settings import PDFSettings, default_pdf_settings
from services.markdown.renderer import render_markdown_to_html
from services.notebook.models import CellType, NotebookCell, NotebookDocument, OutputType
from utils.logging_config import get_logger
from utils.security import sanitize_error

from .styles import build_pdf_css

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "section"


def _logo_img(data: Optional[str], css_class: str = "logo") -> str:
    if not data:
        return ""
    src = data if data.startswith("data:") else f"data:image/png;base64,{data}"
    return f'<img class="{css_class}" src="{src}" alt="logo"/>'


def _highlight_source(source: str, language: str, theme: str) -> str:
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, get_lexer_by_name
        from pygments.util import ClassNotFound

        try:
            lexer = get_lexer_by_name(language, stripall=True)
        except ClassNotFound:
            lexer = TextLexer()
        formatter = HtmlFormatter(
            noclasses=True,
            nowrap=False,
            style=theme or "friendly",
            wrapcode=True,
        )
        return highlight(source, lexer, formatter)
    except Exception:  # noqa: BLE001
        return f"<pre><code>{html.escape(source)}</code></pre>"


def _image_data_uri(mime: str, data_b64: str) -> str:
    payload = data_b64.strip()
    if mime == "image/svg+xml" and payload.lstrip().startswith("<"):
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    if payload.startswith("data:"):
        return payload
    return f"data:{mime};base64,{payload}"


def _render_html_table_fragment(html_frag: str) -> str:
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", html_frag, flags=re.I)
    cleaned = re.sub(r"on\w+\s*=\s*['\"][^'\"]*['\"]", "", cleaned, flags=re.I)
    return f'<div class="html-output">{cleaned}</div>'


def _render_outputs(cell: NotebookCell) -> str:
    chunks: List[str] = []
    for out in cell.outputs:
        if out.output_type == OutputType.ERROR:
            tb = html.escape(out.text or f"{out.ename}: {out.evalue}")
            chunks.append(
                f'<div class="cell-err"><div class="cell-label">Error | {html.escape(out.ename)}</div>'
                f"<pre>{tb}</pre></div>"
            )
            continue

        if out.output_type == OutputType.STREAM and out.name == "stderr":
            chunks.append(
                f'<div class="cell-stderr"><div class="cell-label">stderr</div>'
                f"<pre>{html.escape(out.text)}</pre></div>"
            )
            continue

        for img in out.images:
            uri = _image_data_uri(img["mime"], img["data_b64"])
            chunks.append(f'<img src="{uri}" alt="Notebook output image"/>')

        if out.html and ("<table" in out.html.lower() or "<div" in out.html.lower()):
            chunks.append(_render_html_table_fragment(out.html))
        elif out.text.strip():
            label = "stdout" if out.name == "stdout" else "Output"
            chunks.append(
                f'<div class="cell-out"><div class="cell-label">{label}</div>'
                f"<pre>{html.escape(out.text)}</pre></div>"
            )
    return "".join(chunks)


def _render_cell(cell: NotebookCell, language: str, settings: PDFSettings) -> str:
    if cell.hidden:
        return ""

    theme = settings.syntax_highlight_theme or settings.code_theme

    if cell.cell_type == CellType.MARKDOWN:
        body = render_markdown_to_html(cell.source, default_language=language)
        anchor = ""
        if cell.heading_text:
            anchor = f'<a id="{_slugify(cell.heading_text)}"></a>'
        return (
            f'<div class="cell cell-md">{anchor}'
            f'<div class="cell-label">Markdown</div>{body}</div>'
        )

    if cell.cell_type == CellType.CODE:
        exec_lbl = (
            f'<span class="exec">[{cell.execution_count}]</span>'
            if cell.execution_count is not None
            else ""
        )
        code_html = _highlight_source(cell.source, language, theme)
        outputs = "" if cell.collapsed else _render_outputs(cell)
        return (
            f'<div class="cell cell-code">'
            f'<div class="cell-label">Code {exec_lbl}</div>{code_html}{outputs}</div>'
        )

    return (
        f'<div class="cell cell-raw"><div class="cell-label">Raw</div>'
        f"<pre>{html.escape(cell.source)}</pre></div>"
    )


def render_notebook_body(doc: NotebookDocument, settings: PDFSettings) -> str:
    lang = settings.resolved_language(doc.language)
    return "".join(_render_cell(c, lang, settings) for c in doc.visible_cells())


def render_toc_html(doc: NotebookDocument) -> str:
    """TOC removed from PDF layout — always returns empty."""
    return ""


def _corner_svg(corner: str) -> str:
    """Square navy corner ribbon with gold diagonal stripes (TR + mirrored BL)."""
    tr = (
        '<path d="M0,0 H100 V100 Z" fill="#102D5C"/>'
        '<path d="M22,0 L100,78" fill="none" stroke="#D4AF37" stroke-width="3.6"/>'
        '<path d="M36,0 L100,64" fill="none" stroke="#E9C46A" stroke-width="2.4"/>'
        '<path d="M50,0 L100,50" fill="none" stroke="#D4AF37" stroke-width="1.8"/>'
        '<path d="M12,0 L100,88" fill="none" stroke="#F0D78C" stroke-width="1.1" opacity="0.85"/>'
    )
    bl = (
        '<path d="M100,100 H0 V0 Z" fill="#102D5C"/>'
        '<path d="M78,100 L0,22" fill="none" stroke="#D4AF37" stroke-width="3.6"/>'
        '<path d="M64,100 L0,36" fill="none" stroke="#E9C46A" stroke-width="2.4"/>'
        '<path d="M50,100 L0,50" fill="none" stroke="#D4AF37" stroke-width="1.8"/>'
        '<path d="M88,100 L0,12" fill="none" stroke="#F0D78C" stroke-width="1.1" opacity="0.85"/>'
    )
    art = tr if corner == "tr" else bl
    return (
        f'<div class="cover-corner cover-corner-{corner}">'
        f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">{art}</svg>'
        f"</div>"
    )


def _meta_icon(kind: str) -> str:
    """Solid gold tile icons with white glyphs (reference template)."""
    icons = {
        "author": (
            '<circle cx="8" cy="5.2" r="2.8" fill="#fff"/>'
            '<path d="M2.2 13.5c0-2.8 2.5-4.4 5.8-4.4s5.8 1.6 5.8 4.4" '
            'fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>'
        ),
        "source": (
            '<rect x="3.2" y="2.2" width="9.6" height="11.6" rx="1.4" fill="none" '
            'stroke="#fff" stroke-width="1.4"/>'
            '<path d="M5.2 5.2h5.6M5.2 8h5.6M5.2 10.8h3.6" stroke="#fff" stroke-width="1.15"/>'
        ),
        "cells": (
            '<path d="M2.8 4.2h3.8l1.8 2.8-1.8 2.8H2.8L4.6 7 2.8 4.2zm10.4 0H9.4l1.8 2.8'
            '-1.8 2.8h3.8L11.4 7l1.8-2.8z" fill="none" stroke="#fff" stroke-width="1.35"/>'
        ),
        "version": (
            '<path d="M8 2.1l4.8 1.9v3.8c0 3-2 5.2-4.8 6.1C5.2 13 3.2 10.8 3.2 7.8V4L8 2.1z" '
            'fill="none" stroke="#fff" stroke-width="1.35"/>'
            '<path d="M5.6 7.8l1.7 1.7L10.6 6" fill="none" stroke="#fff" '
            'stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "language": (
            '<circle cx="8" cy="8" r="5.2" fill="none" stroke="#fff" stroke-width="1.35"/>'
            '<path d="M8 2.8v10.4M2.8 8h10.4" stroke="#fff" stroke-width="1.1"/>'
        ),
        "company": (
            '<path d="M3 12.8V5.2h3.6V7h6.4v5.8H3z" fill="none" stroke="#fff" stroke-width="1.35"/>'
            '<path d="M5 12.8V9.6h1.8v3.2M9.2 12.8V8.2H11v4.6" stroke="#fff" stroke-width="1.15"/>'
        ),
    }
    body = icons.get(kind, icons["source"])
    return (
        f'<div class="cover-meta-icon">'
        f'<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">{body}</svg>'
        f"</div>"
    )


def _default_hero_data_uri() -> Optional[str]:
    """Load bundled cover hero PNG from assets/ if present."""
    try:
        hero_path = Path(__file__).resolve().parents[2] / "assets" / "cover_hero.png"
        if not hero_path.is_file():
            return None
        raw = hero_path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def _default_hero_svg() -> str:
    """Fallback laptop / AI illustration SVG."""
    return """
<svg class="cover-hero-svg" viewBox="0 0 640 240" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a1f45"/>
      <stop offset="50%" stop-color="#164988"/>
      <stop offset="100%" stop-color="#0d2a56"/>
    </linearGradient>
  </defs>
  <rect width="640" height="240" fill="url(#hg)"/>
  <g stroke="#4da3ff" stroke-width="1" opacity="0.55">
    <line x1="60" y1="50" x2="140" y2="90"/>
    <line x1="140" y1="90" x2="90" y2="160"/>
    <line x1="560" y1="40" x2="500" y2="100"/>
    <line x1="500" y1="100" x2="580" y2="150"/>
  </g>
  <g fill="#5eb0ff">
    <circle cx="60" cy="50" r="4"/><circle cx="140" cy="90" r="5"/>
    <circle cx="500" cy="100" r="5"/><circle cx="580" cy="150" r="3.5"/>
  </g>
  <rect x="190" y="48" width="260" height="150" rx="10" fill="#1b2f4f" stroke="#D4AF37" stroke-width="2"/>
  <rect x="202" y="60" width="236" height="118" rx="4" fill="#0b1729"/>
  <text x="214" y="82" fill="#7CFFB2" font-size="11" font-family="Consolas,monospace">def to_pdf(nb):</text>
  <text x="226" y="100" fill="#9CDCFF" font-size="11" font-family="Consolas,monospace">html = render(nb)</text>
  <text x="226" y="118" fill="#CE9178" font-size="11" font-family="Consolas,monospace">return export(html)</text>
  <rect x="170" y="198" width="300" height="12" rx="3" fill="#243553" stroke="#D4AF37" stroke-width="1"/>
</svg>
"""


def _ornament() -> str:
    star = (
        '<svg class="cover-star" viewBox="0 0 16 16" width="11" height="11" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<path fill="#D4AF37" d="M8 0.6l1.5 4.6H14.5l-3.8 2.8 1.5 4.6L8 9.8'
        'l-4.2 3 1.5-4.6L1.5 5.2h5z"/>'
        "</svg>"
    )
    return f'<div class="cover-ornament">{star}</div>'


def _cover_page(
    *,
    title: str,
    description: str,
    settings: PDFSettings,
    source_filename: str = "",
    cell_summary: str = "",
) -> str:
    """Fixed premium cover matching the navy/gold reference template."""
    company = (settings.company or "").strip() or "AL-Junaid Tech"
    title = (title or "").strip() or "Jupyter Notebook to PDF Converter"
    description = (description or "").strip() or (
        "AI-powered tool that converts Jupyter notebooks "
        "to professionally formatted PDFs with proper "
        "markdown rendering and beautiful layouts."
    )
    copyright_text = (settings.copyright or "").strip() or (
        f"\u00a9 2026 {company}. All rights reserved."
    )

    if settings.header_logo_b64:
        src = settings.header_logo_b64
        if not src.startswith("data:"):
            src = f"data:image/png;base64,{src}"
        hero_class = "cover-hero cover-hero-upload"
        hero_inner = f'<img class="cover-hero-img" src="{src}" alt="Cover visual"/>'
    else:
        hero_class = "cover-hero"
        bundled = _default_hero_data_uri()
        if bundled:
            # Bundled art is authored for the frame; still use contain so nothing clips
            hero_class = "cover-hero cover-hero-upload"
            hero_inner = (
                f'<img class="cover-hero-img" src="{bundled}" alt="Cover visual"/>'
            )
        else:
            hero_inner = _default_hero_svg()

    # Pairs for 2-column table rows (left, right)
    meta_pairs = [
        (
            ("AUTHOR", settings.author or "Junaid Malik", "author"),
            ("VERSION", settings.version or "1.0.0", "version"),
        ),
        (
            ("SOURCE", source_filename or "notebook.ipynb", "source"),
            ("LANGUAGE", settings.language or "Python", "language"),
        ),
        (
            ("CELLS", cell_summary or "-", "cells"),
            ("COMPANY", company, "company"),
        ),
    ]

    rows_html = []
    for left, right in meta_pairs:
        cells = []
        for label, value, icon in (left, right):
            cells.append(
                "<td>"
                f"{_meta_icon(icon)}"
                f'<div class="cover-meta-text">'
                f'<div class="cover-meta-label">{html.escape(label)}</div>'
                f'<div class="cover-meta-value">{html.escape(str(value).strip())}</div>'
                f"</div></td>"
            )
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    corners = _corner_svg("tr") + _corner_svg("bl")

    return f"""
<section class="cover">
  <div class="cover-frame">
    {corners}
    <div class="cover-header">
      <div class="cover-company">{html.escape(company.upper())}</div>
      {_ornament()}
    </div>
    <div class="{hero_class}">{hero_inner}</div>
    <div class="cover-titles">
      <h1 class="cover-title">{html.escape(title)}</h1>
      <div class="cover-ornament-after-title">{_ornament()}</div>
      <p class="cover-desc">{html.escape(description)}</p>
    </div>
    <div class="cover-rule"></div>
    <table class="cover-meta-table">{"".join(rows_html)}</table>
    <div class="cover-bottom">
      <div class="cover-copyright">{html.escape(copyright_text)}</div>
    </div>
  </div>
</section>
"""


def build_full_html(parsed: Dict[str, Any], settings: PDFSettings) -> str:
    """Build HTML from a ParsedNotebook-like dict (used by LangGraph)."""
    title = settings.resolved_title(
        parsed.get("title") or parsed.get("filename") or "Notebook"
    )
    description = (settings.description or "").strip() or (
        parsed.get("description") or ""
    ).strip()
    css = build_pdf_css(settings)
    header_text = (settings.header_text or "").strip() or title
    watermark = (settings.watermark or "").strip()
    wm_html = (
        f'<div class="watermark">{html.escape(watermark)}</div>' if watermark else ""
    )

    cell_count = int(parsed.get("cell_count") or 0)
    code_cells = int(parsed.get("code_cells") or 0)
    md_cells = int(parsed.get("markdown_cells") or 0)
    cell_summary = ""
    if cell_count:
        cell_summary = f"{cell_count} total · {code_cells} code · {md_cells} markdown"

    cover = _cover_page(
        title=title,
        description=description,
        settings=settings,
        source_filename=str(parsed.get("filename") or ""),
        cell_summary=cell_summary,
    )
    body = parsed.get("cells_html") or ""

    footer_logo = _logo_img(settings.footer_logo_b64, css_class="footer-logo")
    author = html.escape((settings.author or "").strip())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>{html.escape(title)}</title>
  <meta name="author" content="{html.escape(settings.author or '')}"/>
  <meta name="description" content="{html.escape(description or title)}"/>
  <style>{css}</style>
</head>
<body>
  {wm_html}
  {cover}
  <div id="running-header">
    <span class="header-text">{html.escape(header_text)}</span>
  </div>
  <div id="running-footer-left">
    {footer_logo}
    <span class="footer-author">{author}</span>
  </div>
  <div class="report-start">
    <div class="content-shell">{body}</div>
  </div>
</body>
</html>
"""


def notebook_to_html_document(
    doc: NotebookDocument,
    settings: PDFSettings | None = None,
    include_cover: bool = True,
    include_toc: bool = False,
) -> str:
    settings = settings or default_pdf_settings()
    title = settings.resolved_title(doc.title)
    description = settings.resolved_description(doc.description)
    language = settings.resolved_language(doc.language)
    parsed = {
        "filename": doc.filename,
        "title": title,
        "description": description,
        "language": language,
        "cell_count": len(doc.cells),
        "code_cells": doc.code_cell_count,
        "markdown_cells": doc.markdown_cell_count,
        "cells_html": render_notebook_body(doc, settings),
        "toc_html": "",
    }
    html_str = build_full_html(parsed, settings)
    if not include_cover:
        html_str = re.sub(
            r'<section class="cover">[\s\S]*?</section>',
            "",
            html_str,
            count=1,
        )
    return html_str


def _pdf_via_weasyprint(html_str: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html_str, base_url=".").write_pdf()


def _pdf_via_xhtml2pdf(html_str: str) -> bytes:
    from xhtml2pdf import pisa

    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_str), dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError("xhtml2pdf reported rendering errors")
    return buf.getvalue()


def _pdf_via_reportlab_fallback(doc: NotebookDocument, settings: PDFSettings) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer

    pagesize = letter if settings.page_size == "Letter" else A4
    buffer = io.BytesIO()
    title = settings.resolved_title(doc.title)
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=settings.margin_left_cm * cm,
        rightMargin=settings.margin_right_cm * cm,
        topMargin=settings.margin_top_cm * cm,
        bottomMargin=settings.margin_bottom_cm * cm,
        title=title,
        author=settings.author or "",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor(settings.primary_color),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellLabel",
            fontSize=8,
            textColor=colors.HexColor(settings.secondary_color),
            spaceBefore=6,
            spaceAfter=2,
        )
    )
    story = [
        Paragraph(xml_escape(title), styles["CoverTitle"]),
        Paragraph(
            xml_escape(f"{settings.company} | {settings.author}"),
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    for cell in doc.visible_cells():
        if cell.cell_type == CellType.MARKDOWN:
            story.append(Paragraph("Markdown", styles["CellLabel"]))
            for line in cell.source.splitlines() or [""]:
                story.append(Paragraph(xml_escape(line) or "&nbsp;", styles["Normal"]))
        elif cell.cell_type == CellType.CODE:
            story.append(
                Paragraph(f"Code [{cell.execution_count or ' '}]", styles["CellLabel"])
            )
            story.append(Preformatted(cell.source or " ", styles["Code"]))
            for out in cell.outputs:
                if out.text:
                    story.append(Preformatted(out.text[:4000], styles["Code"]))
        story.append(Spacer(1, 4))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d0d5dd"))
        canvas.setLineWidth(0.6)
        y_line = 1.35 * cm
        canvas.line(
            settings.margin_left_cm * cm,
            y_line,
            pagesize[0] - settings.margin_right_cm * cm,
            y_line,
        )
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#667085"))
        y = 1.05 * cm
        canvas.drawString(
            settings.margin_left_cm * cm,
            y,
            (settings.author or "")[:40],
        )
        phone = (settings.phone or settings.footer_text or "")[:28]
        canvas.drawCentredString(pagesize[0] / 2, y, phone)
        canvas.drawRightString(
            pagesize[0] - settings.margin_right_cm * cm,
            y,
            f"Page {_doc.page}",
        )
        canvas.restoreState()

    pdf.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def generate_pdf(
    doc: NotebookDocument,
    settings: PDFSettings | None = None,
    branding: Any = None,  # backward-compat shim
) -> Tuple[bytes, str]:
    """Generate a professional PDF. Returns (pdf_bytes, html_used)."""
    if settings is None and branding is not None:
        # Legacy Branding object -> map into PDFSettings
        settings = PDFSettings(
            title=getattr(branding, "product", "") or doc.title,
            author=getattr(branding, "author", ""),
            company=getattr(branding, "company", ""),
            version=getattr(branding, "version", "1.0.0"),
            copyright=getattr(branding, "copyright", ""),
            watermark=getattr(branding, "watermark", ""),
            primary_color=getattr(branding, "primary", "#1a3a5c"),
            accent_color=getattr(branding, "accent", "#c0a060"),
            secondary_color=getattr(branding, "secondary", "#2e6da4"),
        )
    settings = settings or default_pdf_settings()
    html_str = notebook_to_html_document(doc, settings=settings)

    errors: List[str] = []
    try:
        pdf_bytes = _pdf_via_weasyprint(html_str)
        logger.info("PDF generated with WeasyPrint (%s KB)", len(pdf_bytes) // 1024)
        return pdf_bytes, html_str
    except Exception as exc:  # noqa: BLE001
        msg = sanitize_error(exc)
        logger.warning("WeasyPrint unavailable/failed: %s", msg)
        errors.append(f"weasyprint: {msg}")

    try:
        pdf_bytes = _pdf_via_xhtml2pdf(html_str)
        logger.info("PDF generated with xhtml2pdf (%s KB)", len(pdf_bytes) // 1024)
        return pdf_bytes, html_str
    except Exception as exc:  # noqa: BLE001
        msg = sanitize_error(exc)
        logger.warning("xhtml2pdf unavailable/failed: %s", msg)
        errors.append(f"xhtml2pdf: {msg}")

    try:
        pdf_bytes = _pdf_via_reportlab_fallback(doc, settings)
        logger.info("PDF generated with ReportLab fallback (%s KB)", len(pdf_bytes) // 1024)
        return pdf_bytes, html_str
    except Exception as exc:  # noqa: BLE001
        msg = sanitize_error(exc)
        errors.append(f"reportlab: {msg}")
        raise RuntimeError("All PDF engines failed. " + " | ".join(errors)) from exc
