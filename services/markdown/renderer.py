"""GitHub-flavored Markdown → HTML with syntax highlighting."""

from __future__ import annotations

import html
import re
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

_EMOJI_MAP = {
    ":check:": "✅",
    ":x:": "❌",
    ":warning:": "⚠️",
    ":info:": "ℹ️",
    ":rocket:": "🚀",
    ":book:": "📚",
    ":bulb:": "💡",
    ":star:": "⭐",
    ":fire:": "🔥",
    ":tada:": "🎉",
    ":sparkles:": "✨",
    ":memo:": "📝",
    ":computer:": "💻",
    ":link:": "🔗",
}


def _highlight_code(code: str, language: Optional[str] = None) -> str:
    """Return Pygments-highlighted HTML, falling back to escaped pre."""
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_by_name, guess_lexer
        from pygments.util import ClassNotFound

        try:
            lexer = get_lexer_by_name(language or "text", stripall=True)
        except ClassNotFound:
            try:
                lexer = guess_lexer(code)
            except ClassNotFound:
                lexer = get_lexer_by_name("text")
        formatter = HtmlFormatter(
            noclasses=True,
            style="friendly",
            nowrap=False,
            cssstyles="background:#f4f6f9;border-radius:6px;padding:12px 14px;"
            "overflow-x:auto;font-size:9pt;line-height:1.45;",
        )
        return highlight(code, lexer, formatter)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Pygments highlight failed: %s", exc)
        return f'<pre class="codehilite"><code>{html.escape(code)}</code></pre>'


def _replace_emoji_shortcodes(text: str) -> str:
    for code, glyph in _EMOJI_MAP.items():
        text = text.replace(code, glyph)
    return text


def _enhance_task_lists(html_body: str) -> str:
    """Convert GFM task-list items into checkbox markup."""
    html_body = re.sub(
        r"<li>\s*\[ \]\s*",
        '<li class="task-list-item"><input type="checkbox" disabled/> ',
        html_body,
    )
    html_body = re.sub(
        r"<li>\s*\[x\]\s*",
        '<li class="task-list-item"><input type="checkbox" checked disabled/> ',
        html_body,
        flags=re.I,
    )
    return html_body


def _wrap_admonitions(html_body: str) -> str:
    """Convert blockquotes starting with NOTE/WARNING/etc into callout boxes."""
    patterns = [
        (r"<blockquote>\s*<p>\s*<strong>NOTE:</strong>\s*", '<div class="callout callout-info"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>INFO:</strong>\s*", '<div class="callout callout-info"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>WARNING:</strong>\s*", '<div class="callout callout-warn"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>CAUTION:</strong>\s*", '<div class="callout callout-warn"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>TIP:</strong>\s*", '<div class="callout callout-success"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>SUCCESS:</strong>\s*", '<div class="callout callout-success"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>ERROR:</strong>\s*", '<div class="callout callout-error"><p>'),
        (r"<blockquote>\s*<p>\s*<strong>IMPORTANT:</strong>\s*", '<div class="callout callout-error"><p>'),
    ]
    for start, repl in patterns:
        html_body = re.sub(
            start + r"(.*?)</p>\s*</blockquote>",
            repl + r"\1</p></div>",
            html_body,
            flags=re.I | re.S,
        )
    return html_body


def render_markdown_to_html(source: str, default_language: str = "python") -> str:
    """Render GitHub-flavored Markdown to HTML suitable for PDF/HTML export."""
    if not source or not source.strip():
        return ""

    text = _replace_emoji_shortcodes(source)

    # Lightweight math markers → styled spans (KaTeX not available in PDF CSS engines)
    text = re.sub(
        r"\$\$(.+?)\$\$",
        r'<div class="math">\1</div>',
        text,
        flags=re.S,
    )
    text = re.sub(
        r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
        r'<span class="math">\1</span>',
        text,
    )

    try:
        import markdown as md

        html_body = md.markdown(
            text,
            extensions=[
                "extra",
                "nl2br",
                "sane_lists",
                "toc",
                "fenced_code",
                "tables",
                "footnotes",
                "codehilite",
                "smarty",
            ],
            extension_configs={
                "codehilite": {
                    "guess_lang": True,
                    "noclasses": True,
                    "pygments_style": "friendly",
                },
                "toc": {"permalink": False},
            },
            output_format="html5",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("markdown render failed, using escape fallback: %s", exc)
        return f"<p>{html.escape(text).replace(chr(10), '<br/>')}</p>"

    html_body = _enhance_task_lists(html_body)
    html_body = _wrap_admonitions(html_body)

    def _fence_repl(match: re.Match) -> str:
        lang = match.group(1) or default_language
        code = match.group(2)
        return _highlight_code(code, lang)

    html_body = re.sub(
        r"```(\w*)\n(.*?)```",
        _fence_repl,
        html_body,
        flags=re.S,
    )
    return html_body
