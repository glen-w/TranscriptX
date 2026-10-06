"""Tests for transcription provider registry."""

from __future__ import annotations

from unittest.mock import patch

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

    def test_whisperx_docker_registered(self):
        ids = {p.provider_id for p in get_transcription_providers()}
        assert "whisperx_docker" in ids

    def test_unknown_provider_error(self):
        with pytest.raises(UnknownTranscriptionProviderError):
            get_provider("nonexistent")

    def test_default_provider_fallback_when_configured_unavailable(self):
        options = TranscriptionOptions(
            provider_id="whisperx_docker",
            model="large-v3",
            language="en",
            diarize=False,
        )
        with (
            patch(
                "transcriptx.services.transcription.whisperx_docker_provider.WhisperXDockerProvider.is_available"
            ) as docker_avail,
            patch(
                "transcriptx.services.transcription.whispermlx_provider.WhisperMLXProvider.is_available"
            ) as mlx_avail,
        ):
            from transcriptx.services.transcription.provider import (
                ProviderAvailability,
            )

            docker_avail.return_value = ProviderAvailability(
                available=False, reason="no docker", checks=()
            )
            mlx_avail.return_value = ProviderAvailability(
                available=True, reason=None, checks=()
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
        from transcriptx.services.transcription.provider import ProviderAvailability

        with (
            patch(
                "transcriptx.services.transcription.whisperx_docker_provider.WhisperXDockerProvider.is_available",
                return_value=ProviderAvailability(
                    available=False, reason="no docker", checks=()
                ),
            ),
            patch(
                "transcriptx.services.transcription.whispermlx_provider.WhisperMLXProvider.is_available",
                return_value=ProviderAvailability(
                    available=True, reason=None, checks=()
                ),
            ),
        ):
            provider = resolve_default_provider(options)
        assert provider.provider_id == "whispermlx"


@pytest.mark.unit
def test_any_provider_available_true_when_one_passes() -> None:
    from transcriptx.services.transcription.provider import ProviderAvailability
    from transcriptx.services.transcription.registry import any_provider_available

    with (
        patch(
            "transcriptx.services.transcription.whisperx_docker_provider.WhisperXDockerProvider.is_available",
            return_value=ProviderAvailability(
                available=False, reason="no docker", checks=()
            ),
        ),
        patch(
            "transcriptx.services.transcription.whispermlx_provider.WhisperMLXProvider.is_available",
            return_value=ProviderAvailability(available=True, reason=None, checks=()),
        ),
    ):
        assert any_provider_available() is True


@pytest.mark.unit
def test_any_provider_available_false_when_none_pass() -> None:
    from transcriptx.services.transcription.provider import ProviderAvailability
    from transcriptx.services.transcription.registry import any_provider_available

    unavailable = ProviderAvailability(available=False, reason="nope", checks=())
    with (
        patch(
            "transcriptx.services.transcription.whisperx_docker_provider.WhisperXDockerProvider.is_available",
            return_value=unavailable,
        ),
        patch(
            "transcriptx.services.transcription.whispermlx_provider.WhisperMLXProvider.is_available",
            return_value=unavailable,
        ),
    ):
        assert any_provider_available() is False
