"""Contract tests for resolve_audio_path (find_original first, then output scan)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.voice import audio_io


def test_resolve_audio_path_returns_find_original_hit_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mp3 = tmp_path / "primary.mp3"
    mp3.write_bytes(b"a")
    out = tmp_path / "outputs"
    out.mkdir()
    (out / "noise.mp3").write_bytes(b"b")

    def fake_find(_tp: str) -> Path:
        return mp3

    monkeypatch.setattr(
        "transcriptx.core.utils.file_rename.find_original_audio_file",
        fake_find,
    )
    got = audio_io.resolve_audio_path(
        transcript_path=str(tmp_path / "t.json"), output_dir=str(out)
    )
    assert got == str(mp3)


def test_resolve_audio_path_scans_output_dir_when_find_original_misses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "session_out"
    out.mkdir(parents=True)
    wav = out / "artifact.wav"
    wav.write_bytes(b"1")

    monkeypatch.setattr(
        "transcriptx.core.utils.file_rename.find_original_audio_file",
        lambda _tp: None,
    )
    got = audio_io.resolve_audio_path(
        transcript_path=str(tmp_path / "missing.json"), output_dir=str(out)
    )
    assert got == str(wav)
