"""Transcription provider registry."""

from __future__ import annotations

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.provider import TranscriptionProvider
from transcriptx.services.transcription.whispermlx_provider import WhisperMLXProvider

_PROVIDERS: dict[str, TranscriptionProvider] = {
    WhisperMLXProvider.provider_id: WhisperMLXProvider(),
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
