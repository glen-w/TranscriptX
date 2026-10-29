"""Unit tests for Nemotron vLLM provider (stub mode)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.nemotron_vllm_provider import (
    NemotronVllmProvider,
)


@pytest.mark.unit
def test_nemotron_stub_transcribe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_NEMOTRON_STUB", "1")
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    provider = NemotronVllmProvider()
    opts = TranscriptionOptions(
        provider_id="nemotron_vllm",
        model="nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B",
        language="en",
        diarize=True,
        device="cuda",
    )
    avail = provider.is_available(opts)
    assert avail.available
    result = provider.transcribe(audio, out, opts)
    assert result.success
    assert result.json_path is not None
    assert result.json_path.is_file()


@pytest.mark.unit
def test_nemotron_unavailable_on_darwin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_NEMOTRON_STUB", raising=False)
    monkeypatch.setattr(
        "transcriptx.services.transcription.nemotron_vllm_provider.sys.platform",
        "darwin",
    )
    provider = NemotronVllmProvider()
    opts = TranscriptionOptions(
        provider_id="nemotron_vllm",
        model="nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B",
        language="en",
        diarize=True,
    )
    avail = provider.is_available(opts)
    assert not avail.available
    assert avail.reason is not None
    assert "whispermlx" in avail.reason.lower() or "macos" in avail.reason.lower()


@pytest.mark.unit
def test_nemotron_unavailable_when_endpoint_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_NEMOTRON_STUB", raising=False)
    monkeypatch.setattr(
        "transcriptx.services.transcription.nemotron_vllm_provider.sys.platform",
        "linux",
    )
    monkeypatch.setattr(
        "transcriptx.services.transcription.nemotron_vllm_provider.probe_endpoint",
        lambda *_args, **_kwargs: (False, "Connection refused"),
    )
    provider = NemotronVllmProvider()
    opts = TranscriptionOptions(
        provider_id="nemotron_vllm",
        model="nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B",
        language="en",
        diarize=True,
        device="cuda",
    )
    avail = provider.is_available(opts)
    assert not avail.available
    assert avail.reason is not None
    assert "refused" in avail.reason.lower()
