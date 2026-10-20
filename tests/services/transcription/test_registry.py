"""Tests for transcription provider registry."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.provider import ProviderAvailability
from transcriptx.services.transcription.registry import (
    UnknownTranscriptionProviderError,
    get_provider,
    get_transcription_providers,
    resolve_default_provider,
)


def _is_available_patch_target(provider: object) -> str:
    cls = type(provider)
    return f"{cls.__module__}.{cls.__name__}.is_available"


@contextmanager
def patch_providers_is_available(
    *,
    by_id: dict[str, ProviderAvailability] | None = None,
    default: ProviderAvailability | None = None,
) -> Iterator[None]:
    """Patch ``is_available`` on every registered provider class.

    Keeps registry tests hermetic when CI has Docker (parakeet/whisperx) or stub env.
    """
    if by_id is None and default is None:
        raise ValueError("pass by_id and/or default")
    from contextlib import ExitStack

    _unlisted = ProviderAvailability(
        available=False, reason="test stub", checks=()
    )
    with ExitStack() as stack:
        for provider in get_transcription_providers():
            pid = provider.provider_id
            if by_id is not None and pid in by_id:
                value = by_id[pid]
            elif default is not None:
                value = default
            elif by_id is not None:
                value = _unlisted
            else:
                continue
            stack.enter_context(
                patch(_is_available_patch_target(provider), return_value=value)
            )
        yield


@pytest.mark.unit
class TestRegistry:
    def test_whispermlx_listed(self):
        ids = {p.provider_id for p in get_transcription_providers()}
        assert "whispermlx" in ids

    def test_whisperx_docker_registered(self):
        ids = {p.provider_id for p in get_transcription_providers()}
        assert "whisperx_docker" in ids

    def test_parakeet_docker_registered(self):
        ids = {p.provider_id for p in get_transcription_providers()}
        assert "parakeet_docker" in ids

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
        unavailable = ProviderAvailability(
            available=False, reason="no docker", checks=()
        )
        available = ProviderAvailability(available=True, reason=None, checks=())
        with patch_providers_is_available(
            by_id={"whisperx_docker": unavailable, "whispermlx": available},
        ):
            provider = resolve_default_provider(options)
        assert provider.provider_id == "whispermlx"

    def test_resolve_default_unknown_provider_falls_back(self):
        options = TranscriptionOptions(
            provider_id="nonexistent",
            model="large-v3",
            language="en",
            diarize=False,
        )
        unavailable = ProviderAvailability(
            available=False, reason="no docker", checks=()
        )
        available = ProviderAvailability(available=True, reason=None, checks=())
        with patch_providers_is_available(
            by_id={"whisperx_docker": unavailable, "whispermlx": available},
        ):
            provider = resolve_default_provider(options)
        assert provider.provider_id == "whispermlx"


@pytest.mark.unit
def test_any_provider_available_true_when_one_passes() -> None:
    from transcriptx.services.transcription.registry import any_provider_available

    available = ProviderAvailability(available=True, reason=None, checks=())
    with patch_providers_is_available(by_id={"whispermlx": available}):
        assert any_provider_available() is True


@pytest.mark.unit
def test_any_provider_available_false_when_none_pass() -> None:
    from transcriptx.services.transcription.registry import any_provider_available

    unavailable = ProviderAvailability(available=False, reason="nope", checks=())
    with patch_providers_is_available(default=unavailable):
        assert any_provider_available() is False
