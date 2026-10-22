"""Honest copy for host-orchestrated STT (Compose vs native, provider list)."""

from __future__ import annotations

from pathlib import Path

# whispermlx is a Metal/MLX host binary. Streamlit inside transcriptx-web cannot see it.
WHISPERMLX_COMPOSE_UNAVAILABLE = (
    "whispermlx is a Mac host binary; Streamlit in transcriptx-web cannot see it. "
    "Use Copy command on the host, or a Docker provider (WhisperX / Parakeet)."
)

WHISPERMLX_REQUIRES_MACOS = (
    "whispermlx requires macOS (Apple MLX). Use Copy command or a Docker provider "
    "(WhisperX / Parakeet)."
)

# Watcher auto_transcribe / Settings copy — include every registered in-app provider.
AUTO_TRANSCRIBE_PROVIDER_LIST = (
    "whispermlx on the Mac host (not inside Compose), WhisperX Docker, "
    "or NeMo Parakeet Docker"
)

AUTO_TRANSCRIBE_UNAVAILABLE = (
    f"auto_transcribe requires an available host STT provider "
    f"({AUTO_TRANSCRIBE_PROVIDER_LIST})."
)

RUN_IN_APP_CAPTION = (
    "Host-orchestrated STT: Streamlit calls a local provider only when that "
    "binary or Docker daemon is visible to this process. whispermlx runs on the "
    "Mac host, not inside Compose (transcriptx-web cannot see it). WhisperX Docker "
    "and NeMo Parakeet Docker need a docker CLI visible here. If no provider is "
    "available, use Copy command on the host. Stacks: docs/recipes/stt-stacks."
)

TRANSCRIBE_PAGE_INFO = (
    "Run transcription **in the app** when a provider is visible to this Streamlit "
    "process (whispermlx on the Mac host — not inside Compose — WhisperX Docker, "
    "or NeMo Parakeet Docker), or **copy a command** and run it on the host. "
    "Results are admitted with **Import Transcript** unless you enabled in-app import."
)


def running_in_transcriptx_web_container() -> bool:
    """True when this process is inside a Docker container (Compose GUI)."""
    return Path("/.dockerenv").exists()
