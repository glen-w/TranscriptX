"""Tests for transcription provider registry."""

from __future__ import annotations

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.registry import (
    UnknownTranscriptionProviderError,
    get_provider,
    get_transcription_providers,
    resolve_default_provider,
)


@pytest.mark.unit
class TestRegistry:
    def test_whispermlx_listed(self):
        ids = {p.provider_id for p in get_transcription_providers()}
        assert "whispermlx" in ids

    def test_whisperx_docker_not_registered(self):
        ids = {p.provider_id for p in get_transcription_providers()}
        assert "whisperx_docker" not in ids

    def test_unknown_provider_error(self):
        with pytest.raises(UnknownTranscriptionProviderError):
            get_provider("nonexistent")

    def test_default_provider_fallback_from_unregistered_stub(self):
        options = TranscriptionOptions(
            provider_id="whisperx_docker",
            model="large-v3",
            language="en",
            diarize=False,
        )
        provider = resolve_default_provider(options)
        assert provider.provider_id == "whispermlx"

    def test_resolve_default_unknown_provider_falls_back(self):
        options = TranscriptionOptions(
            provider_id="nonexistent",
            model="large-v3",
            language="en",
            diarize=False,
        )
        provider = resolve_default_provider(options)
        assert provider.provider_id == "whispermlx"
