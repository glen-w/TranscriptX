"""Contract tests for progress panel label customization."""

from __future__ import annotations

import pytest

from transcriptx.web.components.progress_panel import render_progress_panel


@pytest.mark.contract
def test_render_progress_panel_accepts_file_labels(monkeypatch):
    """render_progress_panel must accept unit_label/current_label without error."""
    calls: list[tuple] = []

    class FakeSt:
        @staticmethod
        def success(msg, **kwargs):
            calls.append(("success", msg))

        @staticmethod
        def info(msg, **kwargs):
            calls.append(("info", msg))

        @staticmethod
        def markdown(msg, **kwargs):
            calls.append(("markdown", msg))

        @staticmethod
        def progress(value, text=None):
            calls.append(("progress", value, text))

        @staticmethod
        def caption(msg):
            calls.append(("caption", msg))

    monkeypatch.setattr("transcriptx.web.components.progress_panel.st", FakeSt)

    snapshot = {
        "phase": "running_pipeline",
        "status": "running",
        "current_module": "meeting.wav",
        "completed": 1,
        "skipped": 0,
        "failed": 0,
        "total": 3,
        "pct": 33.0,
        "latest_event": "Processing",
        "recent_logs": [],
        "error": None,
    }
    render_progress_panel(
        snapshot,
        unit_label="files",
        current_label="Current file",
    )
    progress_calls = [c for c in calls if c[0] == "progress"]
    assert progress_calls
    assert "files" in progress_calls[0][2]
