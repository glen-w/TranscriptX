"""
Prompt-free speaker identification workflow. No questionary, rich, click, or typer.

Accepts explicit SpeakerIdentificationRequest, returns structured SpeakerIdentificationResult.
Uses ProgressCallback for status updates.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.requests import SpeakerIdentificationRequest
from transcriptx.app.models.results import SpeakerIdentificationResult
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.database.services.transcript_store_policy import (
    store_transcript_after_speaker_identification,
)
from transcriptx.io import load_segments
from transcriptx.io.speaker_mapping import build_speaker_map
from transcriptx.app.compat import get_current_transcript_path_from_state
from transcriptx.core.utils.file_rename import rename_transcript_after_speaker_mapping


def identify_speakers(
    request: SpeakerIdentificationRequest,
    progress: ProgressCallback | None = None,
) -> SpeakerIdentificationResult:
    """
    Run speaker identification on transcript(s). No prompts, no prints.
    """
    if progress is None:
        progress = NullProgress()

    updated_paths: list[Path] = []
    total_speakers = 0
    errors: list[str] = []

    for path in request.transcript_paths:
        path_str = str(path)
        if not Path(path_str).exists():
            errors.append(f"Transcript file not found: {path_str}")
            continue

        progress.on_stage_start("identifying_speakers")
        progress.on_log(f"Processing {path.name}", level="info")

        try:
            segments = load_segments(path_str)
            speaker_map_result = build_speaker_map(
                segments,
                speaker_map_path=None,
                transcript_path=path_str,
                batch_mode=True,
                auto_generate=False,
                persist_speaker_records=False,
            )

            if speaker_map_result:
                total_speakers += len(speaker_map_result)
                if not request.skip_rename:
                    rename_transcript_after_speaker_mapping(path_str)
                final_path = (
                    get_current_transcript_path_from_state(path_str) or path_str
                )
                if Path(final_path).exists():
                    store_transcript_after_speaker_identification(final_path)
                updated_paths.append(Path(final_path))
            else:
                progress.on_log(
                    f"Speaker identification cancelled for {path.name}", level="warning"
                )
        except Exception as e:
            errors.append(f"{path.name}: {str(e)}")
            progress.on_log(str(e), level="error")

        progress.on_stage_complete("identifying_speakers")

    return SpeakerIdentificationResult(
        success=len(errors) == 0 and len(updated_paths) > 0,
        updated_paths=updated_paths,
        speakers_identified=total_speakers,
        errors=errors,
    )
