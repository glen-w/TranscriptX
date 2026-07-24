"""Unit tests for copyable transcription command generation."""

from __future__ import annotations

import pytest

from transcriptx.services.transcription.command_gen import (
    CommandGenParams,
    TranscriptionTool,
    generate_preview_lines,
    generate_transcription_command,
)


@pytest.mark.unit
def test_whispermlx_single_quotes_spaces() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path="/Users/me/My Audio/meeting.mp3",
        output_dir="/Users/me/My Transcripts",
        diarize=True,
    )
    cmd = generate_transcription_command(params)
    assert "My Audio/meeting.mp3" in cmd.shell or "My\\ Audio" in cmd.shell
    assert "'/Users/me/My Audio/meeting.mp3'" in cmd.shell
    assert "'/Users/me/My Transcripts'" in cmd.shell
    assert "--diarize" in cmd.shell
    assert "subprocess" not in cmd.shell.lower()


@pytest.mark.unit
def test_whispermlx_folder_loop() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_SINGLE,
        input_path="/audio/batch folder",
        output_dir="/out",
        audio_glob="*.wav",
        diarize=False,
    )
    cmd = generate_transcription_command(params)
    assert "folder loop" in cmd.title.lower() or "for f in" in cmd.shell
    assert "'/audio/batch folder'" in cmd.shell
    assert "*.wav" in cmd.shell
    assert "--diarize" not in cmd.shell


@pytest.mark.unit
def test_whispermlx_missing_flags() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path="/src with spaces",
        output_dir="/tx",
        dry_run=True,
        force=True,
        fuzzy_json_match=True,
        model="medium",
        language="de",
    )
    cmd = generate_transcription_command(params)
    assert "whispermlx-missing" in cmd.shell
    assert "--dry-run" in cmd.shell
    assert "--force" in cmd.shell
    assert "--fuzzy-json-match" in cmd.shell
    assert "'/src with spaces'" in cmd.shell
    assert "--whisper-args" in cmd.shell
    assert "medium" in cmd.shell
    assert "de" in cmd.shell


@pytest.mark.unit
def test_whisperx_docker_recipe() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERX_DOCKER,
        input_path="/data/audio",
        output_dir="/data/out",
        device="cuda",
        compute_type="float16",
        diarize=True,
        min_speakers=2,
        max_speakers=8,
    )
    cmd = generate_transcription_command(params)
    assert "docker run" in cmd.shell
    assert "--device" in cmd.shell
    assert "cuda" in cmd.shell
    assert "--diarize" in cmd.shell
    assert "--min_speakers 2" in cmd.shell
    assert "--max_speakers 8" in cmd.shell
    assert "whisperx_json" in "\n".join(generate_preview_lines(params))
    assert "Import Transcript" in cmd.next_step


@pytest.mark.unit
def test_expected_output_format_is_whisperx_json() -> None:
    params = CommandGenParams(
        tool=TranscriptionTool.WHISPERMLX_MISSING,
        input_path="/a",
        output_dir="/b",
    )
    assert params.expected_output_format == "whisperx_json"
    cmd = generate_transcription_command(params)
    assert any("JSON" in n for n in cmd.notes)
