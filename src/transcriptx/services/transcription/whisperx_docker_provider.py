"""WhisperX Docker provider stub (coming soon)."""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.core.utils.paths import PATHS
from transcriptx.services.transcription.provider import (
    ProviderAvailability,
    ProviderCheck,
    ProviderInfo,
)

_PROVIDER_ID = "whisperx_docker"
_RECIPE_PATH = PATHS.project_root / "docs" / "recipes" / "whisperx" / "README.md"


class WhisperXDockerProvider:
    provider_id = _PROVIDER_ID

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=_PROVIDER_ID,
            label="WhisperX (Docker)",
            description="Docker-based WhisperX orchestration (coming soon).",
        )

    @property
    def recipe_path(self) -> Path:
        return _RECIPE_PATH

    def is_available(self, options: TranscriptionOptions) -> ProviderAvailability:
        _ = options
        checks = (
            ProviderCheck(
                key="implementation",
                label="GUI orchestration",
                passed=False,
                message="Coming soon",
            ),
        )
        return ProviderAvailability(
            available=False,
            reason="Coming soon — use the external recipe for now",
            checks=checks,
        )

    def transcribe(
        self,
        audio_path: Path,
        output_dir: Path,
        options: TranscriptionOptions,
    ) -> TranscriptionProviderResult:
        _ = (audio_path, options)
        return TranscriptionProviderResult(
            success=False,
            json_path=None,
            output_dir=output_dir,
            returncode=None,
            stdout_tail=(),
            stderr_tail=(),
            duration_seconds=0.0,
            error="WhisperX Docker GUI orchestration is not implemented yet",
        )
