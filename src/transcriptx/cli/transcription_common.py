"""
Common transcription utilities for TranscriptX CLI workflows.

This module provides shared transcription functionality that can be used
by both single-file and batch workflows to ensure consistency and code reuse.
"""

import os
from pathlib import Path
from typing import Optional

from transcriptx.core.transcription import run_whisperx_compose
from transcriptx.core.transcription_runtime import (
    check_whisperx_compose_service,
    get_docker_whisperx_status,
    start_whisperx_compose_service,
)
from rich import print as rprint

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.cli.transcription_utils_compose import wait_for_whisperx_service

logger = get_logger()


def _has_hf_token(config: object | None) -> bool:
    from transcriptx.core.utils.hf_token import resolve_hf_token

    return bool(resolve_hf_token(config).strip())


def transcribe_with_whisperx(
    audio_file: Path, config: object, *, prompt_for_diarization: bool = True
) -> Optional[str]:
    """
    Common transcription function used by both single-file and batch workflows.

    Handles WhisperX service check, transcription, and returns transcript path.
    This function ensures consistent behavior across different workflow entry points.

    Args:
        audio_file: Path to the audio file to transcribe
        config: Configuration object with transcription settings

    Returns:
        Path to the transcript file if successful, None otherwise

    Note:
        This function follows folder conventions:
        - Audio files should be in or copied to RECORDINGS_DIR
        - Transcripts are saved to DIARISED_TRANSCRIPTS_DIR (data/transcripts/)
    """
    try:
        # Ensure WhisperX service is running
        if not check_whisperx_compose_service():
            logger.info("WhisperX service not running, attempting to start")
            if not start_whisperx_compose_service():
                status, msg = get_docker_whisperx_status()
                rprint(f"\n[red]❌ {msg}[/red]")
                log_error(
                    "TRANSCRIPTION",
                    "Failed to start WhisperX service",
                    f"Audio file: {audio_file}",
                )
                return None

        # Wait for service to be stable
        if not wait_for_whisperx_service(timeout=30):
            logger.warning("WhisperX service may not be stable, attempting to restart")
            if not start_whisperx_compose_service():
                status, msg = get_docker_whisperx_status()
                rprint(f"\n[red]❌ {msg}[/red]")
                log_error(
                    "TRANSCRIPTION",
                    "Failed to start WhisperX service after wait",
                    f"Audio file: {audio_file}",
                )
                return None

        # Final verification
        if not check_whisperx_compose_service():
            status, msg = get_docker_whisperx_status()
            rprint(f"\n[red]❌ {msg}[/red]")
            log_error(
                "TRANSCRIPTION",
                "WhisperX service is not ready",
                f"Audio file: {audio_file}",
            )
            return None

        # If diarization is requested but no HF token is available, ask user.
        diarize_restore = None
        if (
            config
            and getattr(config.transcription, "diarize", True)
            and not _has_hf_token(config)
        ):
            if prompt_for_diarization:
                import questionary

                proceed = questionary.confirm(
                    "No Hugging Face token set. Proceed without diarization?"
                ).ask()
                if not proceed:
                    return None
            diarize_restore = config.transcription.diarize
            config.transcription.diarize = False

        # Run transcription
        logger.info(f"Starting WhisperX transcription for: {audio_file.name}")
        try:
            transcript_path = run_whisperx_compose(audio_file, config)
        finally:
            if diarize_restore is not None:
                config.transcription.diarize = diarize_restore

        if not transcript_path:
            log_error(
                "TRANSCRIPTION",
                "WhisperX returned no transcript",
                f"Audio file: {audio_file}",
            )
            return None

        logger.info(f"Transcription completed successfully: {transcript_path}")
        return transcript_path

    except Exception as e:
        log_error(
            "TRANSCRIPTION",
            f"Unexpected error during transcription: {e}",
            f"Audio file: {audio_file}",
            exception=e,
        )
        return None
