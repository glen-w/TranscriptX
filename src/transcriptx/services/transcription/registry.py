"""Transcription provider registry."""

from __future__ import annotations

from dataclasses import replace

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.provider import TranscriptionProvider
from transcriptx.services.transcription.granite_mlx_provider import (
    GraniteMLXProvider,
)
from transcriptx.services.transcription.whispermlx_provider import WhisperMLXProvider
from transcriptx.services.transcription.parakeet_docker_provider import (
    ParakeetDockerProvider,
)
from transcriptx.services.transcription.whisperx_docker_provider import (
    WhisperXDockerProvider,
)

_PROVIDERS: dict[str, TranscriptionProvider] = {
    WhisperMLXProvider.provider_id: WhisperMLXProvider(),
    WhisperXDockerProvider.provider_id: WhisperXDockerProvider(),
    ParakeetDockerProvider.provider_id: ParakeetDockerProvider(),
    GraniteMLXProvider.provider_id: GraniteMLXProvider(),
}

_DEFAULT_FALLBACK_ID = WhisperMLXProvider.provider_id


class UnknownTranscriptionProviderError(KeyError):
    """Raised when a provider ID is not registered."""


def get_transcription_providers() -> list[TranscriptionProvider]:
    return list(_PROVIDERS.values())


def get_provider(provider_id: str) -> TranscriptionProvider:
    try:
        return _PROVIDERS[provider_id]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDERS))
        raise UnknownTranscriptionProviderError(
            f"Unknown transcription provider '{provider_id}'. Known: {known}"
        ) from exc


def resolve_default_provider(
    options: TranscriptionOptions,
) -> TranscriptionProvider:
    try:
        configured = get_provider(options.provider_id)
        if configured.is_available(options).available:
            return configured
    except UnknownTranscriptionProviderError:
        pass
    for provider in get_transcription_providers():
        if provider.is_available(options).available:
            return provider
    return get_provider(_DEFAULT_FALLBACK_ID)


def _relaxed_options(options: TranscriptionOptions) -> TranscriptionOptions:
    if not options.diarize:
        return options
    return replace(options, diarize=False)


def any_provider_available(
    options: TranscriptionOptions | None = None,
) -> bool:
    """True when at least one registered provider can run on this host."""
    from transcriptx.services.transcription.env import default_transcription_options

    base = options or default_transcription_options()
    candidates = (base, _relaxed_options(base))
    for provider in get_transcription_providers():
        for opts in candidates:
            if provider.is_available(opts).available:
                return True
    return False
