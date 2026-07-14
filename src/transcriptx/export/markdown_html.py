"""Safe Markdown → HTML for self-contained export index summaries.

Moved from transcriptx.utils.export_markdown.

Renders a limited Markdown subset with HTML-escaped text nodes so export pages
can show headings, lists, and emphasis without injecting raw HTML or depending
on CDN/JS Markdown libraries (exports must work over ``file://``).
"""

from __future__ import annotations

import html
import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_UL_RE = re.compile(r"^(\s*)([-*])\s+(.+)$")
_OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.+)$")
_BOLD_ITALIC_RE = re.compile(r"(\*\*\*(.+?)\*\*\*)|(\*\*(.+?)\*\*)|(\*(.+?)\*)")
_CODE_RE = re.compile(r"`([^`]+)`")


def _inline_markdown_to_html(text: str) -> str:
    """Escape text, then apply bold/italic/code markers on escaped content."""
    parts: list[str] = []
    last = 0
    for match in _CODE_RE.finditer(text):
        if match.start() > last:
            parts.append(_emphasis_to_html(html.escape(text[last : match.start()])))
        parts.append(f"<code>{html.escape(match.group(1))}</code>")
        last = match.end()
    if last < len(text):
        parts.append(_emphasis_to_html(html.escape(text[last:])))
    return "".join(parts) if parts else _emphasis_to_html(html.escape(text))


def _emphasis_to_html(escaped: str) -> str:
    """Apply bold/italic to already-escaped text.

    Only ``*`` / ``**`` markers are supported (not underscores) so identifiers
    like run IDs (``20260615_232802_58882865``) are not treated as emphasis.
    """

    def _replace(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            return f"<strong><em>{match.group(2)}</em></strong>"
        if match.group(3) is not None:
            return f"<strong>{match.group(4)}</strong>"
        return f"<em>{match.group(6)}</em>"

    return _BOLD_ITALIC_RE.sub(_replace, escaped)


def _close_lists_to(
    stack: list[dict[str, object]],
    parts: list[str],
    *,
    indent: int,
) -> None:
    """Close list items/containers deeper than ``indent``."""
    while stack and int(stack[-1]["indent"]) > indent:
        frame = stack.pop()
        if frame.get("li_open"):
            parts.append("</li>")
            frame["li_open"] = False
        parts.append(f"</{frame['tag']}>")


def _close_all_lists(stack: list[dict[str, object]], parts: list[str]) -> None:
    _close_lists_to(stack, parts, indent=-1)


def _emit_list_item(
    stack: list[dict[str, object]],
    parts: list[str],
    *,
    tag: str,
    indent: int,
    text_html: str,
) -> None:
    _close_lists_to(stack, parts, indent=indent)

    if stack and int(stack[-1]["indent"]) == indent and stack[-1]["tag"] != tag:
        frame = stack.pop()
        if frame.get("li_open"):
            parts.append("</li>")
        parts.append(f"</{frame['tag']}>")

    if not stack or int(stack[-1]["indent"]) < indent:
        parts.append(f"<{tag}>")
        stack.append({"tag": tag, "indent": indent, "li_open": False})

    frame = stack[-1]
    if frame.get("li_open"):
        parts.append("</li>")
        frame["li_open"] = False
    parts.append(f"<li>{text_html}")
    frame["li_open"] = True


def summary_markdown_to_html(md: str) -> str:
    """Convert a safe Markdown subset to HTML for export summary bodies.

    Supports ATX headings (``#``–``######`` → ``h3``/``h4``), paragraphs,
    unordered/ordered lists (including nested lists), horizontal rules (skipped),
    and inline ``**bold**``, ``*italic*``, and ``code``.

    All user text is HTML-escaped; raw HTML in the source is shown as text.
    """
    if not md or not str(md).strip():
        return ""

    lines = str(md).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parts: list[str] = []
    list_stack: list[dict[str, object]] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        text = " ".join(paragraph).strip()
        paragraph = []
        if text:
            parts.append(f"<p>{_inline_markdown_to_html(text)}</p>")

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            flush_paragraph()
            _close_all_lists(list_stack, parts)
            continue

        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            _close_all_lists(list_stack, parts)
            continue

        heading = _HEADING_RE.match(stripped)
        if heading:
            flush_paragraph()
            _close_all_lists(list_stack, parts)
            level = len(heading.group(1))
            # Nest under page/section h2: map #/## → h3, ###+ → h4
            tag = "h3" if level <= 2 else "h4"
            parts.append(
                f"<{tag}>{_inline_markdown_to_html(heading.group(2).strip())}</{tag}>"
            )
            continue

        ul = _UL_RE.match(raw_line)
        if ul:
            flush_paragraph()
            indent = len(ul.group(1).expandtabs(2))
            _emit_list_item(
                list_stack,
                parts,
                tag="ul",
                indent=indent,
                text_html=_inline_markdown_to_html(ul.group(3).strip()),
            )
            continue

        ol = _OL_RE.match(raw_line)
        if ol:
            flush_paragraph()
            indent = len(ol.group(1).expandtabs(2))
            _emit_list_item(
                list_stack,
                parts,
                tag="ol",
                indent=indent,
                text_html=_inline_markdown_to_html(ol.group(3).strip()),
            )
            continue

        _close_all_lists(list_stack, parts)
        paragraph.append(stripped)

    flush_paragraph()
    _close_all_lists(list_stack, parts)
    return "".join(parts)
