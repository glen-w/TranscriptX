"""Library page audio resolution matches core find_original ordering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.rename import audio_association
from transcriptx.web.page_modules import library as library_mod


def test_resolve_audio_for_transcript_returns_find_original_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "session.json"
    transcript.write_text("{}", encoding="utf-8")
    mp3 = tmp_path / "session.mp3"
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

    resolved = library_mod._resolve_audio_for_transcript(transcript)
    assert resolved is not None
    assert resolved.resolve() == mp3.resolve()
