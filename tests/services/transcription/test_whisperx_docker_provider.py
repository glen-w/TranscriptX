"""Tests for WhisperX Docker provider stub."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.whisperx_docker_provider import (
    WhisperXDockerProvider,
)


@pytest.mark.unit
class TestWhisperXDockerProvider:
    def test_always_unavailable(self):
        provider = WhisperXDockerProvider()
        options = TranscriptionOptions(
            provider_id="whisperx_docker",
            model="large-v3",
            language="en",
            diarize=True,
        )
        availability = provider.is_available(options)
        assert not availability.available
        assert availability.reason

    def test_transcribe_returns_not_implemented(self, tmp_path: Path):
        provider = WhisperXDockerProvider()
        options = TranscriptionOptions(
            provider_id="whisperx_docker",
            model="large-v3",
            language="en",
            diarize=False,
        )
        out_dir = tmp_path / "out"
        audio = tmp_path / "clip.mp3"
        audio.write_bytes(b"x")
        result = provider.transcribe(audio, out_dir, options)
        assert not result.success
        assert result.returncode is None
        assert result.error

    def test_recipe_path_points_at_docs(self):
        provider = WhisperXDockerProvider()
        assert provider.recipe_path.name == "README.md"
        assert "whisperx" in str(provider.recipe_path)
