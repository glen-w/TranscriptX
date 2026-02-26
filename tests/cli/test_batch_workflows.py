"""Tests for batch workflow control flow."""

from __future__ import annotations

from pathlib import Path

from transcriptx.cli import batch_workflows


def test_batch_analysis_no_transcripts(capsys) -> None:
    batch_workflows.run_batch_analysis_pipeline([])
    output = capsys.readouterr().out
    assert "No transcripts to process for analysis" in output


def test_batch_analysis_all_invalid_paths(tmp_path: Path, monkeypatch, capsys) -> None:
    missing_path = tmp_path / "missing.json"

    monkeypatch.setattr(
        batch_workflows,
        "_resolve_transcript_path",
        lambda path: (_ for _ in ()).throw(FileNotFoundError()),
    )
    monkeypatch.setattr(
        batch_workflows,
        "apply_analysis_mode_settings_non_interactive",
        lambda *args, **kwargs: None,
    )

    batch_workflows.run_batch_analysis_pipeline(
        [str(missing_path)],
        analysis_mode="quick",
        selected_modules=["sentiment"],
        skip_speaker_gate=True,
    )
    output = capsys.readouterr().out
    assert "No valid transcripts" in output
