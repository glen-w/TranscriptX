"""Tests for export markdown."""

from __future__ import annotations

from transcriptx.export import summary_markdown_to_html


def test_summary_markdown_renders_headings_and_bold() -> None:
    html = summary_markdown_to_html(
        "## Speaker breakdown\n\n- **Alice**: 58 words\n- **Bob**: 57 words\n"
    )
    assert "##" not in html
    assert "**" not in html
    assert "<h3>Speaker breakdown</h3>" in html
    assert "<strong>Alice</strong>" in html
    assert "<strong>Bob</strong>" in html
    assert html.index("<ul>") < html.index("<li><strong>Alice</strong>")
    assert "</ul>" in html


def test_summary_markdown_nests_lists_inside_parent_li() -> None:
    html = summary_markdown_to_html(
        "1. **Send the report**\n   - Status: open\n   - Owner: Alice\n"
    )
    assert "<ol>" in html
    assert "<strong>Send the report</strong>" in html
    assert html.index("<li><strong>Send the report</strong>") < html.index("<ul>")
    assert html.index("</ul>") < html.index("</li></ol>") or html.index(
        "</ul>"
    ) < html.index("</ol>")
    assert "Status: open" in html
    assert "**" not in html


def test_summary_markdown_escapes_raw_html() -> None:
    html = summary_markdown_to_html("Hello <script>alert(1)</script> **world**")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>world</strong>" in html


def test_summary_markdown_paragraphs_and_code() -> None:
    html = summary_markdown_to_html("First paragraph.\n\nUse `code` here.")
    assert "<p>First paragraph.</p>" in html
    assert "<code>code</code>" in html


def test_summary_markdown_preserves_underscores_in_ids() -> None:
    html = summary_markdown_to_html(
        "Run ID: 20260615_232802_58882865\n\n- **Alice**: ok\n"
    )
    assert "20260615_232802_58882865" in html
    assert "<em>" not in html
    assert "<strong>Alice</strong>" in html


def test_summary_markdown_empty() -> None:
    assert summary_markdown_to_html("") == ""
    assert summary_markdown_to_html("   \n") == ""
