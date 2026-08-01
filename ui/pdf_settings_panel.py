"""PDF Settings panel - all metadata and cover design come from the user."""

from __future__ import annotations

import base64
from typing import Optional

import streamlit as st

from models.pdf_settings import PDFSettings, default_pdf_settings


def _file_to_b64(uploaded) -> Optional[str]:
    if not uploaded:
        return None
    raw = uploaded.read()
    mime = uploaded.type or "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _init_pdf_settings_state() -> None:
    if "pdf_settings" not in st.session_state:
        st.session_state.pdf_settings = default_pdf_settings().model_dump()


def _hex(key: str, fallback: str) -> str:
    val = st.session_state.pdf_settings.get(key) or fallback
    if not isinstance(val, str) or not val.startswith("#") or len(val) < 4:
        return fallback
    return val[:7]


def render_pdf_settings_panel(*, disabled: bool = False) -> PDFSettings:
    """Render the PDF customization panel and return current settings."""
    _init_pdf_settings_state()
    ps = st.session_state.pdf_settings

    with st.expander("PDF Settings", expanded=True):
        st.caption(
            "Cover content and colors are fully user-driven. "
            "Leave optional fields empty to hide them on the cover."
        )

        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input(
                "PDF Title",
                value=ps.get("title", ""),
                disabled=disabled,
                placeholder="AI Research Notebook",
            )
            author = st.text_input(
                "Author Name",
                value=ps.get("author", "Junaid Malik"),
                disabled=disabled,
                placeholder="Junaid Malik",
            )
            version = st.text_input(
                "Version",
                value=ps.get("version", ""),
                disabled=disabled,
                placeholder="1.0.0",
            )
            company = st.text_input(
                "Company Name",
                value=ps.get("company", "AL-Junaid Tech"),
                disabled=disabled,
                placeholder="AL-Junaid Tech",
            )
            header_text = st.text_input(
                "Header Text",
                value=ps.get("header_text", ""),
                disabled=disabled,
                placeholder="Jupyter2PDF",
                help="Centered on content pages only (not the cover branding).",
            )
            watermark = st.text_input(
                "Watermark (optional)",
                value=ps.get("watermark", ""),
                disabled=disabled,
                placeholder="Leave empty to disable",
            )
        with c2:
            description = st.text_area(
                "PDF Description",
                value=ps.get("description", ""),
                disabled=disabled,
                placeholder="Complete documentation for the notebook.",
                height=88,
            )
            language = st.text_input(
                "Language",
                value=ps.get("language", ""),
                disabled=disabled,
                placeholder="Python",
            )
            copyright_text = st.text_input(
                "Copyright",
                value=ps.get("copyright", ""),
                disabled=disabled,
                placeholder="(c) 2026 AL-Junaid Tech. All rights reserved.",
            )
            cover_date = st.text_input(
                "Date (optional)",
                value=ps.get("cover_date", ""),
                disabled=disabled,
                placeholder="July 31, 2026",
                help="Optional metadata only; not shown on the fixed cover template.",
            )
            phone = st.text_input(
                "Phone Number",
                value=ps.get("phone") or ps.get("footer_text", ""),
                disabled=disabled,
                placeholder="+92 300 1234567",
                help="Footer center on content pages.",
            )
            page_size = st.selectbox(
                "Page Size",
                options=["A4", "Letter", "Legal"],
                index=["A4", "Letter", "Legal"].index(ps.get("page_size", "A4"))
                if ps.get("page_size", "A4") in ("A4", "Letter", "Legal")
                else 0,
                disabled=disabled,
            )
            page_orientation = st.selectbox(
                "Orientation",
                options=["portrait", "landscape"],
                index=0 if ps.get("page_orientation", "portrait") == "portrait" else 1,
                disabled=disabled,
            )

        st.markdown("##### Content Theme Colors")
        st.caption(
            "Cover page uses a fixed navy / gold / cream corporate template "
            "(colors are not editable)."
        )
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            primary_color = st.color_picker(
                "Primary Theme Color",
                value=_hex("primary_color", "#1a3a5c"),
                disabled=disabled,
            )
        with col_b:
            accent_color = st.color_picker(
                "Accent Color",
                value=_hex("accent_color", "#c0a060"),
                disabled=disabled,
                help="Used for content page accents.",
            )
        with col_c:
            secondary_color = st.color_picker(
                "Secondary Color",
                value=_hex("secondary_color", "#2e6da4"),
                disabled=disabled,
            )

        st.markdown("##### Typography & layout")
        t1, t2, t3 = st.columns(3)
        with t1:
            font_family = st.selectbox(
                "Font Family",
                options=["Segoe UI", "Georgia", "Helvetica", "Times New Roman"],
                index=["Segoe UI", "Georgia", "Helvetica", "Times New Roman"].index(
                    ps.get("font_family", "Segoe UI")
                )
                if ps.get("font_family", "Segoe UI")
                in ("Segoe UI", "Georgia", "Helvetica", "Times New Roman")
                else 0,
                disabled=disabled,
            )
            font_size = st.slider(
                "Body Font Size (pt)",
                8.0,
                14.0,
                float(ps.get("font_size_pt", 10.5)),
                0.5,
                disabled=disabled,
            )
            theme = st.selectbox(
                "Content Theme",
                options=["classic", "modern", "minimal"],
                index=["classic", "modern", "minimal"].index(ps.get("theme", "classic"))
                if ps.get("theme", "classic") in ("classic", "modern", "minimal")
                else 0,
                disabled=disabled,
            )
        with t2:
            code_theme = st.selectbox(
                "Code / Syntax Theme",
                options=["friendly", "monokai", "default", "murphy"],
                index=["friendly", "monokai", "default", "murphy"].index(
                    ps.get("syntax_highlight_theme", "friendly")
                )
                if ps.get("syntax_highlight_theme", "friendly")
                in ("friendly", "monokai", "default", "murphy")
                else 0,
                disabled=disabled,
            )
            wm_opacity = st.slider(
                "Watermark Opacity",
                0.01,
                0.30,
                float(ps.get("watermark_opacity", 0.05)),
                0.01,
                disabled=disabled or not (watermark or "").strip(),
            )
        with t3:
            wm_position = st.selectbox(
                "Watermark Position",
                options=["diagonal", "center"],
                index=0 if ps.get("watermark_position", "diagonal") == "diagonal" else 1,
                disabled=disabled or not (watermark or "").strip(),
            )
            margin_tb = st.slider(
                "Margin T/B (cm)",
                1.0,
                4.0,
                float(ps.get("margin_top_cm", 2.2)),
                0.1,
                disabled=disabled,
            )
            margin_lr = st.slider(
                "Margin L/R (cm)",
                1.0,
                4.0,
                float(ps.get("margin_left_cm", 1.8)),
                0.1,
                disabled=disabled,
            )

        st.markdown("##### Images")
        l1, l2 = st.columns(2)
        with l1:
            header_logo = st.file_uploader(
                "Cover Hero Image (optional)",
                type=["png", "jpg", "jpeg", "svg", "webp"],
                disabled=disabled,
                key="header_logo_upload",
                help=(
                    "Shown fully inside the cover hero (no cropping). "
                    "Logos, posters, banners, and portraits keep their aspect ratio."
                ),
            )
        with l2:
            footer_logo = st.file_uploader(
                "Footer Logo",
                type=["png", "jpg", "jpeg", "svg", "webp"],
                disabled=disabled,
                key="footer_logo_upload",
                help="Scaled to fit the content-page footer.",
            )

        header_b64 = _file_to_b64(header_logo) or ps.get("header_logo_b64")
        footer_b64 = _file_to_b64(footer_logo) or ps.get("footer_logo_b64")

        settings = PDFSettings(
            title=title or "",
            description=description or "",
            author=author or "",
            version=version or "",
            language=language or "",
            company=company or "",
            copyright=copyright_text or "",
            header_text=header_text or "",
            phone=phone or "",
            footer_text=phone or "",
            header_logo_b64=header_b64,
            footer_logo_b64=footer_b64,
            watermark=watermark or "",
            watermark_opacity=wm_opacity,
            watermark_position=wm_position,  # type: ignore[arg-type]
            page_size=page_size,  # type: ignore[arg-type]
            page_orientation=page_orientation,  # type: ignore[arg-type]
            margin_top_cm=margin_tb,
            margin_bottom_cm=margin_tb,
            margin_left_cm=margin_lr,
            margin_right_cm=margin_lr,
            theme=theme,  # type: ignore[arg-type]
            font_family=font_family,  # type: ignore[arg-type]
            font_size_pt=font_size,
            code_theme=code_theme,  # type: ignore[arg-type]
            syntax_highlight_theme=code_theme,  # type: ignore[arg-type]
            primary_color=primary_color,
            accent_color=accent_color,
            secondary_color=secondary_color,
            cover_date=cover_date or "",
            cover_logo_size_px=224,
        )
        st.session_state.pdf_settings = settings.model_dump()
        return settings
