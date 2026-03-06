"""Tests for no-signal Markdown block."""

from __future__ import annotations

from transcriptx.core.presentation.nothing_found import render_no_signal_md


def test_render_no_signal_md_includes_reason_and_threshold() -> None:
    md = render_no_signal_md(
        "No highlights exceeded the score threshold.",
        threshold="0.6",
        metric="quote_score",
        looked_for=["conflict spikes", "cold opens"],
    )
    assert "No strong signal detected" in md
    assert "No highlights exceeded the score threshold." in md
    assert "quote_score" in md
    assert "0.6" in md
    assert "conflict spikes" in md
