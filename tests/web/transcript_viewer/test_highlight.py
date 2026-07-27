"""Tests for highlight."""

from __future__ import annotations

from transcriptx.web.transcript_viewer.highlight import render_highlight_html


def test_highlight_no_match_returns_text() -> None:
    assert render_highlight_html("Hello world", "zzz") == "Hello world"


def test_highlight_marks_matches_and_escapes() -> None:
    rendered = render_highlight_html("A <tag> and a TAG", "tag")
    assert "<mark>tag</mark>" in rendered.lower()
    assert "&lt;" in rendered


def test_highlight_multiple_nonoverlapping_matches() -> None:
    rendered = render_highlight_html("foo bar foo", "foo")
    assert rendered.count("<mark>foo</mark>") == 2


def test_highlight_preserves_unmatched_prefix_suffix() -> None:
    rendered = render_highlight_html("xxNEEDLEyy", "NEEDLE")
    assert rendered.startswith("xx")
    assert rendered.endswith("yy")
    assert "<mark>NEEDLE</mark>" in rendered
