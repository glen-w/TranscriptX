"""Audio Prep page helpers and thin Streamlit orchestration."""

from __future__ import annotations


import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_audio_prep_path_label_relative_and_fallback(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.audio_prep as mod

    recordings = tmp_path / "recordings"
    nested = recordings / "imports" / "a.wav"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"x")
    monkeypatch.setattr(mod, "RECORDINGS_DIR", recordings)

    assert mod._audio_prep_path_label(nested) == "imports/a.wav"
    outside = tmp_path / "other" / "b.wav"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    assert mod._audio_prep_path_label(outside) == "b.wav"


@pytest.mark.unit
def test_resolve_output_dir_destinations(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.audio_prep as mod

    audio = tmp_path / "rec" / "clip.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"x")
    monkeypatch.setattr(mod, "RECORDINGS_DIR", tmp_path / "recordings")

    assert mod._resolve_output_dir(audio, "same") == audio.parent
    assert mod._resolve_output_dir(audio, "sub") == audio.parent / "preprocessed"
    assert mod._resolve_output_dir(audio, "central") == (
        tmp_path / "recordings" / "preprocessed"
    )


@pytest.mark.unit
def test_render_audio_prep_empty_list_shows_info(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.audio_prep as mod

    infos: list[str] = []
    DummyHomeStreamlit.session_state = {}
    recordings = tmp_path / "recordings"
    recordings.mkdir()

    class _St(DummyHomeStreamlit):
        @staticmethod
        def file_uploader(*_a, **_k):
            return []

        @staticmethod
        def info(msg, **_k):
            infos.append(str(msg))

        @staticmethod
        def fragment(fn=None, **_kwargs):
            if fn is None:

                def _decorator(f):
                    return f

                return _decorator
            return fn

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod.RecordingsService, "list_recordings", lambda *_a, **_k: [])
    monkeypatch.setattr(mod, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(mod, "RECORDINGS_IMPORTS_DIR", recordings / "imports")

    mod.render_audio_prep_page()

    assert infos
    assert "No audio files found" in infos[0]
