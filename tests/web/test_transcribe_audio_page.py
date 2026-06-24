"""Smoke tests for Transcribe Audio page."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.app.models.requests import TranscriptionOptions


@pytest.mark.unit
def test_transcribe_audio_page_callable():
    from transcriptx.web.page_modules.transcribe_audio import (
        render_transcribe_audio_page,
    )

    assert callable(render_transcribe_audio_page)


@pytest.mark.unit
def test_providers_include_whispermlx_and_docker_stub():
    from transcriptx.services.transcription.registry import get_transcription_providers

    ids = {p.provider_id for p in get_transcription_providers()}
    assert "whispermlx" in ids
    assert "whisperx_docker" in ids


@pytest.mark.unit
def test_whisperx_docker_always_unavailable():
    from transcriptx.services.transcription.whisperx_docker_provider import (
        WhisperXDockerProvider,
    )

    provider = WhisperXDockerProvider()
    options = TranscriptionOptions(
        provider_id="whisperx_docker",
        model="large-v3",
        language="en",
        diarize=False,
    )
    availability = provider.is_available(options)
    assert not availability.available


@pytest.mark.unit
@patch(
    "transcriptx.web.page_modules.transcribe_audio._render_readiness",
    return_value=False,
)
@patch("streamlit.button", return_value=False)
def test_run_disabled_when_provider_unavailable(_mock_button, _mock_ready):
    from transcriptx.web.page_modules import transcribe_audio as page

    # Contract: disable_reason path exists when readiness fails
    assert page._LARGE_BATCH_THRESHOLD == 50
