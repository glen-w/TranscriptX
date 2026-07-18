"""Audio Merge page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_audio_merge_empty_recordings_shows_info(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.page_modules.audio_merge as mod

    infos: list[str] = []
    DummyHomeStreamlit.session_state = {}
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    imports = recordings / "imports"
    imports.mkdir()

    class _St(DummyHomeStreamlit):
        @staticmethod
        def file_uploader(*_a, **_k):
            return []

        @staticmethod
        def info(msg, **_k):
            infos.append(str(msg))

        @staticmethod
        def markdown(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(mod, "RECORDINGS_IMPORTS_DIR", imports)
    monkeypatch.setattr(mod.RecordingsService, "list_recordings", lambda *_a, **_k: [])
    section_calls: list = []
    monkeypatch.setattr(
        mod, "_render_section_1", lambda *_a, **_k: section_calls.append(True)
    )
    monkeypatch.setattr(mod, "_render_detected_serial_groups", lambda *_a, **_k: None)

    mod.render_audio_merge_page()

    assert infos
    assert "No audio files found" in infos[0]
    assert section_calls == []


@pytest.mark.unit
def test_audio_merge_with_recordings_renders_section(
    monkeypatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.audio_merge as mod

    DummyHomeStreamlit.session_state = {}
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    imports = recordings / "imports"
    imports.mkdir()
    clip = recordings / "a.wav"
    clip.write_bytes(b"x")

    class _St(DummyHomeStreamlit):
        @staticmethod
        def file_uploader(*_a, **_k):
            return []

        @staticmethod
        def markdown(*_a, **_k):
            return None

    section_calls: list = []
    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(mod, "RECORDINGS_IMPORTS_DIR", imports)
    monkeypatch.setattr(
        mod.RecordingsService,
        "list_recordings",
        lambda root: [clip] if root == recordings else [],
    )
    monkeypatch.setattr(
        mod, "_render_section_1", lambda recs: section_calls.append(list(recs))
    )
    monkeypatch.setattr(mod, "_render_detected_serial_groups", lambda *_a, **_k: None)

    mod.render_audio_merge_page()

    assert section_calls
    assert clip in section_calls[0]
