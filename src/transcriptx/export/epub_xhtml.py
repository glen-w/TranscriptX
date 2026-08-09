"""Strict XHTML helpers for EPUB export chapters."""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from transcriptx.export.markdown_html import summary_markdown_to_html

_UNSAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def xml_escape(text: str) -> str:
    return escape(str(text), {"'": "&apos;", '"': "&quot;"})


def slugify_chapter_id(raw: str, *, fallback: str = "section") -> str:
    """Deterministic filesystem-/href-safe chapter id stem."""
    text = str(raw or "").strip().lower().replace(" ", "-")
    text = _UNSAFE_ID_RE.sub("-", text).strip("-")
    if not text:
        text = fallback
    if text[0].isdigit():
        text = f"s-{text}"
    return text[:80]


class ChapterIdAllocator:
    """Allocate unique chapter IDs with collision suffixes."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def allocate(self, preferred: str, *, fallback: str = "section") -> str:
        base = slugify_chapter_id(preferred, fallback=fallback)
        candidate = base
        n = 2
        while candidate in self._used:
            candidate = f"{base}-{n}"
            n += 1
        self._used.add(candidate)
        return candidate


def wrap_epub_xhtml(
    *,
    title: str,
    body: str,
    css_href: str = "styles.css",
) -> str:
    """Build a complete EPUB3 XHTML document (UTF-8, XML-safe)."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!DOCTYPE html>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        f"<title>{xml_escape(title)}</title>\n"
        f'<link rel="stylesheet" type="text/css" href="{xml_escape(css_href)}" />\n'
        "</head>\n"
        f"<body>\n{body}\n</body>\n"
        "</html>\n"
    )


def summary_markdown_to_xhtml(md: str) -> str:
    """Convert the export Markdown subset to an XHTML body fragment."""
    html_frag = summary_markdown_to_html(md)
    if not html_frag:
        return ""
    # Subset emitter already escapes text; ensure void-style self-closing if any
    # sneaks in later. Current subset has no void tags.
    return html_frag


def provenance_meta_bits(provenance: dict | None) -> list[str]:
    provenance = provenance or {}
    bits: list[str] = []
    model = provenance.get("model")
    provider = provenance.get("provider")
    if model:
        bits.append(f"Model: {model}")
    if provider:
        bits.append(f"Provider: {provider}")
    if provenance.get("truncated"):
        bits.append("Input truncated")
    return bits
