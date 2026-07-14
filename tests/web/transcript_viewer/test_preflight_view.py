"""Tests for preflight view."""

from __future__ import annotations

from transcriptx.web.page_modules.transcript import _render_preflight_empty_state
from transcriptx.web.transcript_viewer.preflight import ViewerPreflight


def test_preflight_empty_state_no_subject(monkeypatch) -> None:
    captured = {}

    def _capture(*_args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "transcriptx.web.page_modules.transcript.render_empty_state",
        _capture,
    )
    _render_preflight_empty_state(ViewerPreflight(status="no_subject"))
    assert captured.get("primary_action") == ("Open Library", "Library")
