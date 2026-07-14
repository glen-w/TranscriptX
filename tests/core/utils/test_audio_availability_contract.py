"""Contract tests: audio availability delegates to find_original_audio_file first."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.audio_availability import has_resolvable_audio
from transcriptx.core.utils.rename import audio_association


def test_has_resolvable_audio_true_when_processing_state_audio_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "meet.json"
    transcript.write_text("{}", encoding="utf-8")
    mp3 = tmp_path / "meet.mp3"
    mp3.write_bytes(b"x")

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "f5e5bd96-aef4-4b4a-ad44-5c96aa120337": {
                        "transcript_path": str(transcript),
                        "mp3_path": str(mp3),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(audio_association, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(audio_association, "RECORDINGS_DIR", tmp_path / "rec")
    monkeypatch.setattr(audio_association, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "rec").mkdir()

    assert has_resolvable_audio(str(transcript)) is True


def test_has_resolvable_audio_false_when_no_state_and_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "orphan.json"
    transcript.write_text("{}", encoding="utf-8")
    state_file = tmp_path / "processing_state.json"
    state_file.write_text(json.dumps({"processed_files": {}}), encoding="utf-8")

    monkeypatch.setattr(audio_association, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(audio_association, "RECORDINGS_DIR", tmp_path / "rec")
    monkeypatch.setattr(audio_association, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "rec").mkdir()

    monkeypatch.setattr(
        "transcriptx.core.utils.audio_availability.find_original_audio_file",
        lambda _tp: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.audio_availability.resolve_audio_path",
        lambda **_: None,
    )

    assert has_resolvable_audio(str(transcript)) is False
