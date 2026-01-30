from __future__ import annotations

from dataclasses import dataclass

from transcriptx.core.transcription_runtime import check_whisperx_compose_service

WHISPERX_START_COMMAND = (
    "docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx"
)


@dataclass(frozen=True)
class ProbeResult:
    available: bool
    label: str
    detail: str
    start_command: str | None = None


def probe_whisperx() -> ProbeResult:
    available = check_whisperx_compose_service()
    if available:
        return ProbeResult(
            available=True,
            label="WhisperX (container)",
            detail="WhisperX container is running.",
        )
    return ProbeResult(
        available=False,
        label="WhisperX (container)",
        detail="WhisperX container is not running.",
        start_command=WHISPERX_START_COMMAND,
    )


def probe_whispercpp() -> ProbeResult:
    return ProbeResult(
        available=False,
        label="whisper.cpp (planned)",
        detail="Planned — not implemented in this build.",
    )
