"""Unit tests for transcript_output directory safety redirects."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.utils import transcript_output as transcript_output_module
from transcriptx.core.utils.transcript_output import generate_human_friendly_transcript


@pytest.fixture
def _mute_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcript_output_module, "notify_user", lambda *a, **k: None)


def test_generate_human_friendly_transcript_redirects_from_transcripts_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mute_notify: None
) -> None:
    """Paths under DIARISED_TRANSCRIPTS_DIR must not receive outputs; use OUTPUTS_DIR."""
    outputs = tmp_path / "outputs"
    transcripts = tmp_path / "transcripts"
    outputs.mkdir()
    transcripts.mkdir()
    bad_dir = transcripts / "raw"
    bad_dir.mkdir()

    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts)
    )

    segments = [{"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0}]
    result = generate_human_friendly_transcript(segments, "meet", str(bad_dir))

    assert result["status"] == "success"
    expected_base = outputs / "meet" / "transcripts"
    assert Path(result["transcript_file"]).is_file()
    assert Path(result["csv_file"]).is_file()
    assert Path(result["srt_file"]).is_file()
    assert expected_base in Path(result["transcript_file"]).parents


def test_generate_human_friendly_transcript_redirects_when_outside_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mute_notify: None
) -> None:
    """If transcript_dir is not under OUTPUTS_DIR, coerce to OUTPUTS_DIR / base_name."""
    outputs = tmp_path / "outputs"
    elsewhere = tmp_path / "somewhere_else"
    outputs.mkdir()
    elsewhere.mkdir()

    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path / "tx")
    )

    segments = [{"speaker": "Bob", "text": "Hi", "start": 0.0, "end": 0.5}]
    result = generate_human_friendly_transcript(segments, "session", str(elsewhere))

    assert result["status"] == "success"
    assert (outputs / "session" / "transcripts").exists()
    assert Path(result["transcript_file"]).is_file()
    assert Path(result["srt_file"]).is_file()


def test_generate_human_friendly_transcript_uses_outputs_subdir_when_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _mute_notify: None
) -> None:
    """Valid layout: transcript_dir already under OUTPUTS_DIR — write under .../transcripts/."""
    outputs = tmp_path / "outputs"
    run_dir = outputs / "slug" / "run1"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path / "tx")
    )

    segments = [{"speaker": "C", "text": "ok", "start": 0.0, "end": 1.0}]
    result = generate_human_friendly_transcript(segments, "meet", str(run_dir))

    assert result["status"] == "success"
    out_txt = Path(result["transcript_file"])
    out_srt = Path(result["srt_file"])
    assert "transcripts" in out_txt.parts
    assert run_dir in out_txt.parents
    assert out_srt.is_file()
    assert run_dir in out_srt.parents
