"""Tests for library metadata duration fallback behavior."""

from __future__ import annotations

from pathlib import Path


def test_get_transcript_metadata_uses_segment_duration_fallback(monkeypatch) -> None:
    import transcriptx.app.controllers.library_controller as mod

    controller = mod.LibraryController()
    transcript_path = Path("/tmp/sample.json")

    monkeypatch.setattr(
        "transcriptx.core.audio.get_audio_duration",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "transcriptx.io.load_segments",
        lambda _path: [
            {"start": 1.0, "end": 3.0, "speaker": "S1"},
            {"start": 4.0, "end": 8.5, "speaker": "S2"},
        ],
    )
    monkeypatch.setattr(mod, "named_speaker_count_for_path", lambda _p: 0)
    monkeypatch.setattr(mod, "_has_analysis_outputs", lambda _p: False)
    monkeypatch.setattr(mod, "_has_speaker_map", lambda _p: False)
    monkeypatch.setattr(mod, "_linked_run_dirs", lambda _p: [])

    meta = controller.get_transcript_metadata(transcript_path)

    assert meta.duration_seconds == 7.5
    assert meta.speaker_count == 2


def test_get_transcript_metadata_keeps_duration_none_when_segments_invalid(
    monkeypatch,
) -> None:
    import transcriptx.app.controllers.library_controller as mod

    controller = mod.LibraryController()
    transcript_path = Path("/tmp/sample.json")

    monkeypatch.setattr(
        "transcriptx.core.audio.get_audio_duration",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "transcriptx.io.load_segments",
        lambda _path: [
            {"start": None, "end": 3.0, "speaker": "S1"},
            {"start": 10.0, "end": 2.0, "speaker": "S2"},
            {"start": "bad", "end": "data", "speaker": None},
        ],
    )
    monkeypatch.setattr(mod, "named_speaker_count_for_path", lambda _p: 0)
    monkeypatch.setattr(mod, "_has_analysis_outputs", lambda _p: False)
    monkeypatch.setattr(mod, "_has_speaker_map", lambda _p: False)
    monkeypatch.setattr(mod, "_linked_run_dirs", lambda _p: [])

    meta = controller.get_transcript_metadata(transcript_path)

    assert meta.duration_seconds is None
    assert meta.speaker_count == 2
