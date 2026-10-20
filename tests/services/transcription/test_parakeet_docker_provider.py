"""Unit tests for Parakeet Docker provider (stub mode)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.parakeet_docker_provider import (
    ParakeetDockerProvider,
)


@pytest.mark.unit
def test_parakeet_stub_transcribe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_PARAKEET_STUB", "1")
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    provider = ParakeetDockerProvider()
    opts = TranscriptionOptions(
        provider_id="parakeet_docker",
        model="nvidia/parakeet-tdt-0.6b-v3",
        language="en",
        diarize=False,
        device="cpu",
    )
    avail = provider.is_available(opts)
    assert avail.available
    result = provider.transcribe(audio, out, opts)
    assert result.success
    assert result.json_path is not None
    assert result.json_path.is_file()
