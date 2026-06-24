"""Transcription provider protocol and availability types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult


@dataclass(frozen=True)
class ProviderInfo:
    provider_id: str
    label: str
    description: str


@dataclass(frozen=True)
class ProviderCheck:
    key: str
    label: str
    passed: bool
    message: str | None = None


@dataclass(frozen=True)
class ProviderAvailability:
    available: bool
    reason: str | None
    checks: tuple[ProviderCheck, ...]


class TranscriptionProvider(Protocol):
    provider_id: str

    def info(self) -> ProviderInfo: ...

    def is_available(self, options: TranscriptionOptions) -> ProviderAvailability: ...

    def transcribe(
        self,
        audio_path: Path,
        output_dir: Path,
        options: TranscriptionOptions,
    ) -> TranscriptionProviderResult: ...
