"""Professional PDF stylesheet - minimal header, clean footer, premium cover."""

from __future__ import annotations

from models.pdf_settings import PDFSettings
from .cover_template import build_fixed_cover_css


def _escape_css_content(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", "")
    )


def build_pdf_css(settings: PDFSettings) -> str:
    """Return print-optimized CSS using user PDF settings."""
    page = settings.page_size
    orientation = getattr(settings, "page_orientation", "portrait") or "portrait"
    page_size_css = f"{page} {orientation}".strip()
    mt, mb = settings.margin_top_cm, settings.margin_bottom_cm
    ml, mr = settings.margin_left_cm, settings.margin_right_cm
    primary = settings.primary_color
    accent = settings.accent_color
    secondary = settings.secondary_color
    font = settings.font_family
    fsize = settings.font_size_pt
    phone = _escape_css_content(
        (settings.phone or settings.footer_text or "").strip()
    )
    wm_opacity = settings.watermark_opacity
    wm_transform = (
        "translate(-50%, -50%) rotate(-34deg)"
        if settings.watermark_position == "diagonal"
        else "translate(-50%, -50%)"
    )

    # Theme-dependent header rule
    if settings.theme == "minimal":
        header_border = "border-bottom: none;"
    elif settings.theme == "modern":
        header_border = "border-bottom: 1px solid #e5e7eb;"
    else:
        header_border = f"border-bottom: 1px solid {accent};"

    # Fixed cover inset / height (cover colors are locked in cover_template)
    cover_inset = 0.55
    orient = (orientation or "portrait").lower()
    if page == "Letter":
        cover_min_height = "9.2in" if orient == "portrait" else "6.8in"
    elif page == "Legal":
        cover_min_height = "12.2in" if orient == "portrait" else "6.8in"
    else:  # A4
        cover_min_height = "250mm" if orient == "portrait" else "170mm"

    cover_css = build_fixed_cover_css(cover_min_height)

    return f"""
@page {{
  size: {page_size_css};
  margin: {mt}cm {mr}cm {mb}cm {ml}cm;
  @top-center {{
    content: element(running-header);
    width: 100%;
  }}
  @bottom-left {{
    content: element(running-footer-left);
    width: 34%;
    vertical-align: middle;
    border-top: 0.6pt solid #d0d5dd;
    padding-top: 6px;
  }}
  @bottom-center {{
    content: "{phone}";
    font-family: '{font}', Helvetica, Arial, sans-serif;
    font-size: 7.5pt;
    color: #667085;
    width: 32%;
    text-align: center;
    vertical-align: middle;
    border-top: 0.6pt solid #d0d5dd;
    padding-top: 6px;
    white-space: nowrap;
    overflow: hidden;
  }}
  @bottom-right {{
    content: "Page " counter(page);
    font-family: '{font}', Helvetica, Arial, sans-serif;
    font-size: 7.5pt;
    color: #667085;
    width: 34%;
    text-align: right;
    vertical-align: middle;
    border-top: 0.6pt solid #d0d5dd;
    padding-top: 6px;
    white-space: nowrap;
  }}
}}

@page :first {{
  margin: {cover_inset}cm;
  @top-center {{ content: none; }}
  @bottom-left {{ content: none; border: none; padding: 0; }}
  @bottom-center {{ content: none; border: none; padding: 0; }}
  @bottom-right {{ content: none; border: none; padding: 0; }}
}}

* {{ box-sizing: border-box; }}

html, body {{
  margin: 0;
  padding: 0;
  font-family: '{font}', Helvetica, Arial, sans-serif;
  font-size: {fsize}pt;
  line-height: 1.5;
  color: #1f2933;
  background: #fff;
}}

/* ---- Running header: ONE centered text only ---- */
#running-header {{
  position: running(running-header);
  width: 100%;
  text-align: center;
  {header_border}
  padding: 0 0 7px 0;
}}
#running-header .header-text {{
  display: inline-block;
  font-size: 9.5pt;
  font-weight: 600;
  letter-spacing: 0.4px;
  color: {primary};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}}

/* ---- Running footer left: author + optional logo ---- */
#running-footer-left {{
  position: running(running-footer-left);
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: '{font}', Helvetica, Arial, sans-serif;
  font-size: 7.5pt;
  color: #667085;
  white-space: nowrap;
  overflow: hidden;
  max-width: 100%;
}}
#running-footer-left .footer-author {{
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
#running-footer-left img.footer-logo {{
  height: 12px !important;
  width: auto !important;
  max-height: 12px !important;
  max-width: 48px !important;
  object-fit: contain !important;
  border: none !important;
  margin: 0 !important;
  border-radius: 0 !important;
  display: inline-block !important;
  vertical-align: middle;
  flex-shrink: 0;
}}

.watermark {{
  position: fixed;
  top: 42%;
  left: 50%;
  transform: {wm_transform};
  font-size: 52pt;
  color: rgba(26, 58, 92, {wm_opacity});
  font-weight: 700;
  letter-spacing: 2px;
  white-space: nowrap;
  z-index: 0;
  pointer-events: none;
}}

/* ---- Fixed premium cover (navy / gold / cream) ---- */
{cover_css}

/* ---- Content ---- */
.report-start {{
  position: relative;
  z-index: 1;
}}

.content-shell {{
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  padding: 14px 16px;
  background: #fff;
  position: relative;
  z-index: 1;
  overflow: hidden;
}}

h1, h2, h3, h4, h5, h6 {{
  color: {primary};
  line-height: 1.25;
  margin: 0.75em 0 0.35em;
  page-break-after: avoid;
  break-after: avoid;
  orphans: 3;
  widows: 3;
}}
h1 {{
  font-size: 15pt;
  border-bottom: 1.5px solid {accent};
  padding-bottom: 4px;
}}
h2 {{
  font-size: 12.5pt;
  border-left: 3px solid {secondary};
  padding-left: 8px;
}}
h3 {{ font-size: 11pt; color: {secondary}; }}
h4 {{ font-size: 10.5pt; color: #334; }}

p {{
  margin: 0.35em 0;
  text-align: justify;
  orphans: 3;
  widows: 3;
}}
a {{ color: {secondary}; text-decoration: none; }}
blockquote {{
  border-left: 3px solid {accent};
  margin: 6px 0;
  padding: 4px 10px;
  background: #fffdf6;
  color: #445;
  font-style: italic;
  page-break-inside: avoid;
}}
ul, ol {{ margin: 4px 0 4px 18px; padding: 0; }}
li {{ margin: 2px 0; orphans: 2; widows: 2; }}
li.task-list-item {{ list-style: none; margin-left: -1em; }}

code {{
  font-family: Consolas, 'Courier New', monospace;
  background: #eef2f7;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 0.9em;
  word-break: break-word;
}}
pre, .highlight, .highlight pre {{
  background: #f4f6f9 !important;
  border: 1px solid #d0d8e8;
  border-radius: 6px;
  padding: 8px 10px !important;
  margin: 0 !important;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: pre-wrap !important;
  font-size: 8.5pt;
  line-height: 1.4;
  max-width: 100%;
  page-break-inside: avoid;
  break-inside: avoid;
}}

table {{
  width: 100%;
  max-width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 9pt;
  table-layout: fixed;
  page-break-inside: avoid;
  break-inside: avoid;
}}
th {{
  background: {primary};
  color: #fff;
  text-align: left;
  padding: 5px 8px;
}}
td {{
  padding: 4px 8px;
  border: 1px solid #d5dbe3;
  word-break: break-word;
  overflow-wrap: anywhere;
}}
tr:nth-child(even) td {{ background: #f5f7fb; }}

img {{
  max-width: 100% !important;
  height: auto !important;
  display: block;
  margin: 8px auto;
  border: 1px solid #e4e7ec;
  border-radius: 4px;
  object-fit: contain;
  page-break-inside: avoid;
  break-inside: avoid;
}}

.cell {{
  margin: 6px 0;
  page-break-inside: avoid;
  break-inside: avoid;
  overflow: hidden;
  max-width: 100%;
}}
.cell-label {{
  font-size: 6.8pt;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin: 0 0 3px;
}}
.cell-md {{
  background: #fffdf8;
  border: 1px solid #eee6d6;
  border-left: 3px solid {accent};
  border-radius: 6px;
  padding: 8px 10px;
}}
.cell-md .cell-label {{ color: {accent}; }}
.cell-md > :first-child {{ margin-top: 0; }}
.cell-md > :last-child {{ margin-bottom: 0; }}
.cell-md h1:first-child,
.cell-md h2:first-child,
.cell-md h3:first-child {{ margin-top: 0; }}

.cell-code {{
  background: #f4f6f9;
  border: 1px solid #d0d8e8;
  border-left: 3px solid {secondary};
  border-radius: 6px;
  padding: 8px 10px;
  overflow: hidden;
}}
.cell-code .cell-label {{ color: {secondary}; }}
.cell-code .exec {{
  float: right;
  font-size: 7pt;
  color: #889;
  font-weight: 600;
}}
.cell-code pre,
.cell-code .highlight,
.cell-code .highlight pre {{
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  margin: 0 !important;
}}

.cell-out, .cell-err, .cell-stderr {{
  border-radius: 6px;
  padding: 6px 9px;
  margin-top: 4px;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 8pt;
  white-space: pre-wrap !important;
  overflow-wrap: anywhere;
  word-break: break-word;
  max-width: 100%;
  overflow: hidden;
  page-break-inside: avoid;
}}
.cell-out {{
  background: #f7fff7;
  border: 1px solid #b8ddb8;
  border-left: 3px solid #3a8a3a;
  color: #1a3a1a;
}}
.cell-out .cell-label {{ color: #3a8a3a; font-family: '{font}', sans-serif; }}
.cell-err {{
  background: #fff5f5;
  border: 1px solid #e8b4b4;
  border-left: 3px solid #c0564a;
  color: #7a1f1f;
}}
.cell-err .cell-label {{ color: #c0564a; font-family: '{font}', sans-serif; }}
.cell-stderr {{
  background: #fffaf0;
  border: 1px solid #edd9a8;
  border-left: 3px solid #c9942c;
  color: #6a4a10;
}}
.cell-raw {{
  background: #f8f8f8;
  border: 1px dashed #bbb;
  border-radius: 6px;
  padding: 8px 10px;
  font-family: monospace;
  font-size: 9pt;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}}

.html-output {{
  max-width: 100%;
  overflow: hidden;
  margin: 4px 0;
}}
.html-output table {{ margin: 4px 0; }}

.callout {{
  border-radius: 6px;
  padding: 7px 10px;
  margin: 6px 0;
  font-size: 9pt;
  page-break-inside: avoid;
}}
.callout-info {{ background: #eef4fb; border: 1px solid {secondary}; color: {primary}; }}
.callout-warn {{ background: #fff8e8; border: 1px solid #c9942c; color: #6a4a10; }}
.callout-success {{ background: #eefaf0; border: 1px solid #3a8a3a; color: #1f5a2a; }}
.callout-error {{ background: #fff0f0; border: 1px solid #c0564a; color: #7a1f1f; }}

.math {{ font-style: italic; color: #223; }}
"""
