"""Tests for WhisperX Docker provider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.whisperx_docker_provider import (
    WhisperXDockerProvider,
)


def _options(**kwargs) -> TranscriptionOptions:
    values = dict(
        provider_id="whisperx_docker",
        model="large-v3",
        language="en",
        diarize=False,
    )
    values.update(kwargs)
    return TranscriptionOptions(**values)


@pytest.mark.unit
class TestWhisperXDockerProvider:
    def test_unavailable_without_docker(self):
        provider = WhisperXDockerProvider()
        with patch(
            "transcriptx.services.transcription.whisperx_docker_provider.resolve_docker_binary",
            return_value=None,
        ):
            availability = provider.is_available(_options())
        assert not availability.available
        assert availability.reason

    def test_available_when_docker_and_daemon_ok(self):
        provider = WhisperXDockerProvider()
        with (
            patch(
                "transcriptx.services.transcription.whisperx_docker_provider.resolve_docker_binary",
                return_value=Path("/usr/bin/docker"),
            ),
            patch(
                "transcriptx.services.transcription.whisperx_docker_provider._docker_daemon_ok",
                return_value=(True, None),
            ),
        ):
            availability = provider.is_available(_options(diarize=False))
        assert availability.available

    def test_transcribe_invokes_docker_run(self, tmp_path: Path):
        provider = WhisperXDockerProvider()
        audio = tmp_path / "clip.mp3"
        audio.write_bytes(b"x")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        json_path = out_dir / "clip.json"
        json_path.write_text("{}", encoding="utf-8")
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate.return_value = ("ok", "")
        with (
            patch(
                "transcriptx.services.transcription.whisperx_docker_provider.resolve_docker_binary",
                return_value=Path("/usr/bin/docker"),
            ),
            patch(
                "transcriptx.services.transcription.whisperx_docker_provider.subprocess.Popen",
                return_value=proc,
            ) as popen,
        ):
            result = provider.transcribe(audio, out_dir, _options(device="cuda"))
        assert result.success
        assert result.json_path == json_path
        argv = popen.call_args[0][0]
        assert argv[0] == "/usr/bin/docker"
        assert "run" in argv
        assert "--gpus" in argv
        assert "whisperx" in argv
        assert "/audio/clip.mp3" in argv

    def test_recipe_path_points_at_docs(self):
        provider = WhisperXDockerProvider()
        assert provider.recipe_path.name == "README.md"
        assert "whisperx" in str(provider.recipe_path)
