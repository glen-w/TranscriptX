"""Unit tests for the local Nemotron vLLM client (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from transcriptx.services.transcription.nemotron_json_to_whisperx import (
    segments_from_payload,
)
from transcriptx.services.transcription.nemotron_vllm_client import (
    build_prompt,
    is_loopback_base_url,
    probe_endpoint,
    transcribe_file,
)


@pytest.mark.unit
def test_loopback_urls() -> None:
    assert is_loopback_base_url("http://127.0.0.1:8000/v1")
    assert is_loopback_base_url("http://localhost:8000/v1")
    assert not is_loopback_base_url("https://api.nvidia.com/v1")


@pytest.mark.unit
def test_prompt_keywords_and_diarize() -> None:
    speaker = build_prompt(diarize=True, keywords=("NATO",))
    assert "<spk:0>" in speaker
    assert "Context terms: NATO" in speaker
    written = build_prompt(diarize=False)
    assert "transcript only" in written.lower()
    assert "<spk:0>" not in written


@pytest.mark.unit
def test_transcribe_file_mocked_http(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF")
    payload = {
        "choices": [{"message": {"content": "<spk:0> Hello <spk:1> Hi"}}],
        "ctc_timestamps": {
            "error": None,
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.4, "speaker": 0},
                {"word": "Hi", "start": 0.5, "end": 0.8, "speaker": 1},
            ],
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    response = MagicMock()
    response.read.return_value = raw
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch(
        "transcriptx.services.transcription.nemotron_vllm_client.urllib.request.urlopen",
        return_value=response,
    ):
        dump = transcribe_file(audio, diarize=True)
    segments = segments_from_payload(dump)
    assert [s["speaker"] for s in segments] == ["SPEAKER_00", "SPEAKER_01"]


@pytest.mark.unit
def test_transcribe_refuses_remote_url(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF")
    with pytest.raises(ValueError, match="loopback"):
        transcribe_file(
            audio,
            base_url="https://example.invalid/v1",
            env={},
        )


@pytest.mark.unit
def test_probe_connection_refused() -> None:
    with patch(
        "transcriptx.services.transcription.nemotron_vllm_client.urllib.request.urlopen",
        side_effect=URLError("Connection refused"),
    ):
        ok, message = probe_endpoint("http://127.0.0.1:8000/v1")
    assert not ok
    assert "refused" in message.lower() or "connection" in message.lower()


@pytest.mark.unit
def test_probe_rejects_remote_without_allow() -> None:
    ok, message = probe_endpoint("https://example.invalid/v1", env={})
    assert not ok
    assert "loopback" in message.lower()


@pytest.mark.unit
def test_allow_remote_reaches_http() -> None:
    from unittest.mock import MagicMock

    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch(
        "transcriptx.services.transcription.nemotron_vllm_client.urllib.request.urlopen",
        return_value=response,
    ):
        ok, message = probe_endpoint(
            "https://gpu.example.invalid/v1",
            env={"TRANSCRIPTX_NEMOTRON_ALLOW_REMOTE": "1"},
        )
    assert ok
    assert "reachable" in message
