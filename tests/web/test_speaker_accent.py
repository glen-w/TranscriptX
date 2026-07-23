"""Tests for shared per-speaker accent helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.speaker_accent import (
    SPEAKER_ACCENTS,
    speaker_accent_color,
    speaker_chip_html,
    speaker_heading_html,
    speaker_inline_html,
)


@pytest.mark.unit
def test_speaker_accent_color_cycles_by_index() -> None:
    first = speaker_accent_color(0)
    second = speaker_accent_color(1)
    assert first != second
    assert first.startswith("#")
    assert speaker_accent_color(len(SPEAKER_ACCENTS)) == first


@pytest.mark.unit
def test_speaker_accent_color_stable_by_name() -> None:
    assert speaker_accent_color("Alice") == speaker_accent_color(" alice ")
    assert speaker_accent_color("Alice") != speaker_accent_color("Bob")


@pytest.mark.unit
def test_speaker_heading_html_includes_swatch_and_accent() -> None:
    html = speaker_heading_html("Alice", meta="3 segments")
    assert 'class="tx-speaker-heading"' in html
    assert 'class="tx-speaker-swatch"' in html
    assert "Alice" in html
    assert "3 segments" in html
    assert "--speaker-accent:" in html


@pytest.mark.unit
def test_speaker_chip_and_inline_html() -> None:
    chip = speaker_chip_html("Bob")
    assert 'class="tx-speaker-chip"' in chip
    assert 'class="tx-speaker-swatch"' in chip
    assert "Bob" in chip
    inline = speaker_inline_html("Carol")
    assert 'class="tx-speaker-inline"' in inline
    assert "Carol" in inline
    assert speaker_inline_html("") == ""
    assert speaker_inline_html("   ") == ""
