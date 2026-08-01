"""User-configurable PDF document settings (no hardcoded branding)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PDFSettings(BaseModel):
    """All PDF metadata and visual options come from the user."""

    title: str = Field(default="", description="PDF document title")
    description: str = Field(default="", description="Cover / subtitle description")
    author: str = Field(default="Junaid Malik", description="Document author")
    version: str = Field(default="1.0.0", description="Document version")
    language: str = Field(default="Python", description="Primary language label")
    company: str = Field(default="AL-Junaid Tech", description="Company / organization")
    copyright: str = Field(
        default="\u00a9 2026 AL-Junaid Tech. All rights reserved.",
        description="Copyright line",
    )
    header_text: str = Field(default="", description="Centered running header text")
    phone: str = Field(default="", description="Phone number shown in footer center")
    footer_text: str = Field(
        default="",
        description="Deprecated alias for phone; prefer phone",
    )
    header_logo_b64: Optional[str] = Field(
        default=None,
        description="Optional cover hero image (replaces built-in illustration)",
    )
    footer_logo_b64: Optional[str] = Field(
        default=None, description="Optional footer logo as data-URI or base64 PNG"
    )
    watermark: str = Field(
        default="",
        description="Watermark text; empty disables watermark rendering",
    )
    watermark_opacity: float = Field(default=0.05, ge=0.01, le=0.3)
    watermark_position: Literal["center", "diagonal"] = "diagonal"
    page_size: Literal["A4", "Letter", "Legal"] = "A4"
    page_orientation: Literal["portrait", "landscape"] = "portrait"
    margin_top_cm: float = Field(default=2.2, ge=1.0, le=4.0)
    margin_bottom_cm: float = Field(default=2.6, ge=1.0, le=4.0)
    margin_left_cm: float = Field(default=1.8, ge=1.0, le=4.0)
    margin_right_cm: float = Field(default=1.8, ge=1.0, le=4.0)
    theme: Literal["classic", "modern", "minimal"] = "classic"
    font_family: Literal["Segoe UI", "Georgia", "Helvetica", "Times New Roman"] = (
        "Segoe UI"
    )
    font_size_pt: float = Field(default=10.5, ge=8.0, le=14.0)
    code_theme: Literal["friendly", "monokai", "default", "murphy"] = "friendly"
    syntax_highlight_theme: Literal["friendly", "monokai", "default", "murphy"] = (
        "friendly"
    )
    primary_color: str = Field(default="#1a3a5c", description="Primary theme color")
    accent_color: str = Field(
        default="#c0a060", description="Accent for content pages"
    )
    secondary_color: str = Field(default="#2e6da4")

    # Legacy cover color fields (ignored - cover theme is locked in cover_template)
    cover_date: str = Field(
        default="",
        description="Optional cover date; unused by the fixed template",
    )
    cover_bg_color: str = Field(default="#FFFEFA")
    cover_border_color: str = Field(default="#D4AF37")
    cover_border_width_pt: float = Field(default=2.8, ge=0.0, le=8.0)
    cover_border_radius_pt: float = Field(default=22.0, ge=0.0, le=28.0)
    cover_title_color: str = Field(default="#102D5C")
    cover_description_color: str = Field(default="#555555")
    cover_text_color: str = Field(default="#102D5C")
    cover_inset_cm: float = Field(
        default=0.55,
        ge=0.25,
        le=1.5,
        description="Inset of the cover border from page edges",
    )
    cover_logo_size_px: int = Field(
        default=224,
        ge=64,
        le=320,
        description="Legacy field; hero image uses full-width frame",
    )

    def resolved_title(self, fallback: str) -> str:
        return (self.title or "").strip() or fallback

    def resolved_description(self, fallback: str) -> str:
        return (self.description or "").strip() or fallback

    def resolved_language(self, fallback: str) -> str:
        return (self.language or "").strip() or fallback


def default_pdf_settings() -> PDFSettings:
    """Defaults for the PDF Settings panel."""
    return PDFSettings()
