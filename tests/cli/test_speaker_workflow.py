"""Tests for speaker workflow control flow."""

from __future__ import annotations

from pathlib import Path

from transcriptx.cli import speaker_workflow


def test_speaker_workflow_success(tmp_path: Path, monkeypatch, capsys) -> None:
    transcript_file = tmp_path / "sample.json"
    transcript_file.write_text('{"segments": []}')

    monkeypatch.setattr(
        speaker_workflow, "select_folder_interactive", lambda start_path: tmp_path
    )
    monkeypatch.setattr(
        speaker_workflow, "select_files_interactive", lambda files, config: [transcript_file]
    )
    monkeypatch.setattr(
        speaker_workflow, "load_segments", lambda path: [{"speaker": "A", "text": "hi"}]
    )
    monkeypatch.setattr(
        speaker_workflow, "build_speaker_map", lambda *args, **kwargs: {"A": "A"}
    )
    monkeypatch.setattr(
        speaker_workflow, "rename_transcript_after_speaker_mapping", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        speaker_workflow, "get_current_transcript_path_from_state", lambda path: str(transcript_file)
    )
    monkeypatch.setattr(
        speaker_workflow, "store_transcript_after_speaker_identification", lambda *args, **kwargs: None
    )

    speaker_workflow._run_speaker_identification_workflow_impl()
    output = capsys.readouterr().out
    assert "Speaker identification completed" in output
