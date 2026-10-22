"""Compose vs native STT honesty copy."""

from __future__ import annotations

from transcriptx.services.transcription.honesty import (
    AUTO_TRANSCRIBE_PROVIDER_LIST,
    AUTO_TRANSCRIBE_UNAVAILABLE,
    RUN_IN_APP_CAPTION,
    TRANSCRIBE_PAGE_INFO,
    WHISPERMLX_COMPOSE_UNAVAILABLE,
    running_in_transcriptx_web_container,
)


def test_auto_transcribe_copy_names_parakeet_and_compose_limit() -> None:
    assert "parakeet" in AUTO_TRANSCRIBE_PROVIDER_LIST.lower()
    assert "Compose" in AUTO_TRANSCRIBE_PROVIDER_LIST
    assert "parakeet" in AUTO_TRANSCRIBE_UNAVAILABLE.lower()


def test_run_in_app_copy_says_compose_cannot_see_whispermlx() -> None:
    assert "transcriptx-web cannot see it" in RUN_IN_APP_CAPTION
    assert "whispermlx" in TRANSCRIBE_PAGE_INFO
    assert "not inside Compose" in TRANSCRIBE_PAGE_INFO
    assert "Parakeet" in TRANSCRIBE_PAGE_INFO
    assert "transcriptx-web" in WHISPERMLX_COMPOSE_UNAVAILABLE


def test_container_probe_is_boolean() -> None:
    assert isinstance(running_in_transcriptx_web_container(), bool)
