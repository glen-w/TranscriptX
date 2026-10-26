"""Source contracts for the G5 Transcribe Audio capture panel."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web import icons as ic
from transcriptx.web.ui import capture_panel


@pytest.mark.unit
def test_capture_panel_uses_registry_icons():
    source = Path(capture_panel.__file__).read_text(encoding="utf-8")
    assert "icon=ic.PLAY" in source
    assert "icon=ic.STOP" in source
    assert ic.PLAY.startswith(":material/")
    assert "subprocess" not in source
    assert "Popen" not in source


@pytest.mark.unit
def test_transcribe_page_mounts_capture_panel():
    from transcriptx.web.page_modules import transcribe_audio as page

    source = Path(page.__file__).read_text(encoding="utf-8")
    assert "render_system_audio_capture_panel" in source
    assert "subprocess" not in source
    assert "Popen" not in source


@pytest.mark.unit
def test_panel_compose_caption_when_unavailable(monkeypatch):
    monkeypatch.setattr(capture_panel, "capture_controls_available", lambda: False)
    captions: list[str] = []
    monkeypatch.setattr(capture_panel.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(
        capture_panel.st, "caption", lambda msg, **k: captions.append(str(msg))
    )
    capture_panel.render_system_audio_capture_panel()
    assert captions
    assert "Mac host" in captions[0]
    assert "Docker Compose" in captions[0]


@pytest.mark.unit
def test_panel_start_stop_visible_on_darwin(monkeypatch):
    monkeypatch.setattr(capture_panel, "capture_controls_available", lambda: True)
    monkeypatch.setattr(capture_panel, "list_capture_status", lambda: None)
    labels: list[str] = []

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(capture_panel.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(capture_panel.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(capture_panel.st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(capture_panel.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(
        capture_panel.st,
        "button",
        lambda label, **k: labels.append(str(label)) or False,
    )
    monkeypatch.setattr(capture_panel.st, "columns", lambda n: (_Col(), _Col()))
    capture_panel.render_system_audio_capture_panel()
    assert "Start capture" in labels
    assert "Stop capture" in labels
