"""Smoke tests for Transcribe Audio page."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions


@pytest.mark.unit
def test_transcribe_audio_page_callable():
    from transcriptx.web.page_modules.transcribe_audio import (
        render_transcribe_audio_page,
    )

    assert callable(render_transcribe_audio_page)


@pytest.mark.unit
def test_transcribe_audio_page_is_instruction_only():
    import transcriptx.web.page_modules.transcribe_audio as page

    source = Path(page.__file__).read_text(encoding="utf-8")
    assert "whispermlx-missing" in source
    assert "Import Transcript" in source
    assert "st.file_uploader" not in source
    assert "TranscriptionController" not in source


@pytest.mark.unit
def test_providers_include_whispermlx_only():
    from transcriptx.services.transcription.registry import get_transcription_providers

    ids = {p.provider_id for p in get_transcription_providers()}
    assert "whispermlx" in ids
    assert "whisperx_docker" not in ids


@pytest.mark.unit
def test_whisperx_docker_provider_file_still_unavailable():
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
