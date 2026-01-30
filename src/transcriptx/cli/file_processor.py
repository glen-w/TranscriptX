"""
Single file processing pipeline for batch workflows.

This module provides functions for processing individual WAV files through
the complete pipeline: conversion, transcription, type detection, and tag extraction.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from transcriptx.cli.audio import (
    convert_wav_to_mp3,
    backup_wav_after_processing,
    get_mp3_name_for_wav_backup,
)
from transcriptx.cli.audio_fingerprinting import (
    compute_audio_fingerprint,
    compute_fingerprint_hash,
    get_or_create_file_entity,
)
from transcriptx.cli.processing_state import (
    mark_file_processed,
)
from transcriptx.cli.transcription_common import transcribe_with_whisperx
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import RECORDINGS_DIR, DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.path_utils import resolve_file_path
from transcriptx.io.transcript_loader import load_segments

logger = get_logger()


def _offer_and_edit_tags(*args, **kwargs):
    from transcriptx.cli.tag_workflow import offer_and_edit_tags

    return offer_and_edit_tags(*args, **kwargs)


def _store_tags_in_database(*args, **kwargs):
    from transcriptx.cli.tag_workflow import store_tags_in_database

    return store_tags_in_database(*args, **kwargs)


def _get_tracking_service():
    from transcriptx.database import get_session, FileTrackingService

    session = get_session()
    return session, FileTrackingService(session)


def _resolve_transcript_path(transcript_path: str) -> str:
    """
    Resolve a transcript path to an existing file.

    This function uses the unified path resolution system.

    Args:
        transcript_path: Original transcript path (may be just filename or full path)

    Returns:
        Resolved path to existing transcript file

    Raises:
        FileNotFoundError: If transcript file cannot be found
    """
    return resolve_file_path(
        transcript_path, file_type="transcript", validate_state=True
    )


def _store_metadata_in_database(
    transcript_path: str,
    conversation_type: Optional[str],
    type_confidence: float,
    tags: List[str],
    tag_details: Dict[str, Any],
) -> None:
    """
    Store conversation type and tags in database.

    This is a wrapper around the centralized store_tags_in_database function
    for backward compatibility.

    Args:
        transcript_path: Path to transcript file (may be old path if file was renamed)
        conversation_type: Detected conversation type
        type_confidence: Confidence score for type detection
        tags: List of extracted tags
        tag_details: Detailed tag information
    """
    _store_tags_in_database(
        transcript_path,
        tags,
        tag_details,
        conversation_type=conversation_type,
        type_confidence=type_confidence,
    )


def _offer_tag_editing(transcript_path: str) -> None:
    """
    Offer tag editing for a transcript after speaker identification and renaming.

    This is a wrapper around the centralized offer_and_edit_tags function
    for backward compatibility.

    Args:
        transcript_path: Path to the transcript file (may be old path if file was renamed)
    """
    _offer_and_edit_tags(transcript_path, batch_mode=False, auto_prompt=True)


def process_single_file(
    wav_path: Path, preprocessing_decisions: Dict[Path, Dict[str, bool]] | None = None
) -> Dict[str, Any]:
    """
    Process a single WAV file through the full pipeline.

    Pipeline: Convert → Transcribe → Detect Type → Extract Tags

    Args:
        wav_path: Path to WAV file
        preprocessing_decisions: Optional dict mapping file paths to preprocessing decisions
            Format: {Path: {"denoise": bool, "highpass": bool, ...}}

    Returns:
        Dictionary with processing results and metadata
    """
    result = {
        "file": str(wav_path),
        "status": "pending",
        "steps": {},
        "file_entity_id": None,  # Track entity ID through pipeline
        "pipeline_run_id": str(uuid4()),  # Group all events from this run
    }

    try:
        # Step 0: File Ingestion - Compute fingerprint and create/retrieve entity
        logger.info(f"Ingesting {wav_path.name}...")
        try:
            fingerprint = compute_audio_fingerprint(wav_path)
            if fingerprint is None:
                logger.warning(
                    f"Could not compute fingerprint for {wav_path.name}, skipping tracking"
                )
                file_entity_id = None
            else:
                fingerprint_hash = compute_fingerprint_hash(fingerprint)
                file_entity = get_or_create_file_entity(
                    fingerprint_hash=fingerprint_hash,
                    fingerprint_vector=fingerprint,
                    file_path=wav_path,
                )
                file_entity_id = file_entity.id
                result["file_entity_id"] = file_entity_id

                # Create original artifact and log ingestion event
                session, tracking_service = _get_tracking_service()
                try:
                    # Get file stats
                    stat = wav_path.stat()
                    size_bytes = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime)

                    # Create original artifact
                    original_artifact = tracking_service.create_artifact(
                        file_entity_id=file_entity_id,
                        path=str(wav_path.resolve()),
                        file_type="wav",
                        role="original",
                        size_bytes=size_bytes,
                        mtime=mtime,
                        is_current=True,
                        is_present=True,
                    )

                    # Log ingestion event
                    tracking_service.log_ingestion(
                        file_entity_id=file_entity_id,
                        artifact_id=original_artifact.id,
                        pipeline_run_id=result["pipeline_run_id"],
                    )

                    session.commit()
                    logger.debug(
                        f"✅ Tracked file ingestion: entity_id={file_entity_id}"
                    )
                except Exception as tracking_error:
                    session.rollback()
                    logger.warning(
                        f"File tracking failed (non-critical): {tracking_error}"
                    )
                    # Continue processing even if tracking fails
        except Exception as e:
            logger.warning(f"Fingerprint computation failed for {wav_path.name}: {e}")
            file_entity_id = None
            # Continue processing even if fingerprinting fails

        # Step 1: Convert WAV to MP3
        logger.info(f"Converting {wav_path.name} to MP3...")
        output_dir = Path(RECORDINGS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get preprocessing decisions for this file if provided
        file_preprocessing_decisions = None
        if preprocessing_decisions and wav_path in preprocessing_decisions:
            file_preprocessing_decisions = preprocessing_decisions[wav_path]

        try:
            mp3_path = convert_wav_to_mp3(
                wav_path,
                output_dir,
                preprocessing_decisions=file_preprocessing_decisions,
                file_entity_id=file_entity_id,
                pipeline_run_id=result["pipeline_run_id"],
            )
            result["steps"]["convert"] = {
                "status": "success",
                "mp3_path": str(mp3_path),
            }
        except Exception as e:
            result["steps"]["convert"] = {"status": "failed", "error": str(e)}
            result["status"] = "failed"
            result["error"] = f"Conversion failed: {e}"
            mark_file_processed(
                wav_path,
                {
                    "status": "failed",
                    "error": result["error"],
                    "mp3_path": None,  # Explicitly set to None for failed conversion
                    "transcript_path": None,  # Explicitly set to None for failed conversion
                    **result["steps"],
                },
            )
            return result

        # Step 2: Transcribe with WhisperX
        logger.info(f"Transcribing {mp3_path.name} with WhisperX...")
        config = get_config()

        try:
            transcript_path = transcribe_with_whisperx(mp3_path, config)
            if not transcript_path:
                # Provide more helpful error message with diagnostic suggestions
                error_msg = (
                    "WhisperX returned no transcript. "
                    "This usually means WhisperX completed but couldn't find the output file. "
                    "Possible causes:\n"
                    "  - WhisperX failed silently (check container logs)\n"
                    "  - Output file was created in unexpected location\n"
                    "  - File system sync delay (try running again)\n"
                    "  - Audio file format or corruption issues\n\n"
                    "Diagnostic steps:\n"
                    f"  1. Check container logs: docker logs transcriptx-whisperx\n"
                    f"  2. Verify audio file exists: ls -lh {mp3_path}\n"
                    f"  3. Check output directory: ls -lh {DIARISED_TRANSCRIPTS_DIR}\n"
                    f"  4. Review application logs for detailed error information"
                )
                logger.error(error_msg)
                raise Exception(error_msg)
            result["steps"]["transcribe"] = {
                "status": "success",
                "transcript_path": transcript_path,
            }

            # Track transcription in database
            if file_entity_id:
                try:
                    session, tracking_service = _get_tracking_service()

                    # Find MP3 artifact by path
                    mp3_artifact = tracking_service.artifact_repo.find_by_path(
                        str(mp3_path.resolve())
                    )
                    if not mp3_artifact:
                        # Try to find current MP3 artifact for this entity
                        current_artifacts = tracking_service.get_current_artifacts(
                            file_entity_id, role="mp3"
                        )
                        if current_artifacts:
                            mp3_artifact = current_artifacts[0]

                    if mp3_artifact:
                        # Get transcript file stats
                        transcript_path_obj = Path(transcript_path)
                        if transcript_path_obj.exists():
                            stat = transcript_path_obj.stat()
                            size_bytes = stat.st_size
                            mtime = datetime.fromtimestamp(stat.st_mtime)

                            # Create transcript artifact
                            transcript_artifact = tracking_service.create_artifact(
                                file_entity_id=file_entity_id,
                                path=str(transcript_path_obj.resolve()),
                                file_type="json",
                                role="transcript",
                                size_bytes=size_bytes,
                                mtime=mtime,
                                is_current=True,
                                is_present=True,
                            )

                            # Log transcription event
                            tracking_service.log_transcription(
                                file_entity_id=file_entity_id,
                                source_artifact_id=mp3_artifact.id,
                                target_artifact_id=transcript_artifact.id,
                                pipeline_run_id=result["pipeline_run_id"],
                            )

                            session.commit()
                            logger.debug(
                                f"✅ Tracked transcription: entity_id={file_entity_id}, transcript_artifact_id={transcript_artifact.id}"
                            )
                except Exception as tracking_error:
                    session.rollback()
                    logger.warning(
                        f"Transcription tracking failed (non-critical): {tracking_error}"
                    )
                    # Continue even if tracking fails
        except Exception as e:
            result["steps"]["transcribe"] = {"status": "failed", "error": str(e)}
            result["status"] = "failed"
            result["error"] = f"Transcription failed: {e}"
            # Include mp3_path since conversion succeeded, but transcript_path is None
            mark_file_processed(
                wav_path,
                {
                    "status": "failed",
                    "error": result["error"],
                    "mp3_path": str(
                        mp3_path
                    ),  # Include mp3_path since conversion succeeded
                    "transcript_path": None,  # Explicitly set to None for failed transcription
                    **result["steps"],
                },
            )
            return result

        # Step 3: Detect conversation type
        logger.info(f"Detecting conversation type for {Path(transcript_path).name}...")
        try:
            segments = load_segments(transcript_path)
            speaker_count = len(set(segment.get("speaker", "") for segment in segments))

            from transcriptx.core.analysis.conversation_type import detect_conversation_type

            type_result = detect_conversation_type(segments, speaker_count)
            result["steps"]["detect_type"] = {
                "status": "success",
                "type": type_result["type"],
                "confidence": type_result["confidence"],
                "evidence": type_result["evidence"],
            }
        except Exception as e:
            logger.warning(f"Type detection failed for {transcript_path}: {e}")
            result["steps"]["detect_type"] = {"status": "failed", "error": str(e)}

        # Step 4: Extract tags
        logger.info(f"Extracting tags for {Path(transcript_path).name}...")
        try:
            segments = load_segments(transcript_path)
            from transcriptx.core.analysis.tag_extraction import extract_tags

            tag_result = extract_tags(segments)
            result["steps"]["extract_tags"] = {
                "status": "success",
                "tags": tag_result.get("tags", []),
                "tag_details": tag_result.get("tag_details", {}),
            }
        except Exception as e:
            logger.warning(f"Tag extraction failed for {transcript_path}: {e}")
            result["steps"]["extract_tags"] = {"status": "failed", "error": str(e)}

        # Mark as completed
        result["status"] = "success"

        # Extract metadata
        conversation_type = result["steps"].get("detect_type", {}).get("type")
        tags = result["steps"].get("extract_tags", {}).get("tags", [])
        type_confidence = result["steps"].get("detect_type", {}).get("confidence", 0.0)
        tag_details = result["steps"].get("extract_tags", {}).get("tag_details", {})

        # Store in processing state
        mark_file_processed(
            wav_path,
            {
                "status": "completed",
                "mp3_path": str(mp3_path),
                "transcript_path": transcript_path,
                "conversation_type": conversation_type,
                "tags": tags,
                "type_confidence": type_confidence,
                "tag_details": tag_details,
                **result["steps"],
            },
        )

        # Store in database if available
        _store_metadata_in_database(
            transcript_path, conversation_type, type_confidence, tags, tag_details
        )

        # Automatically backup WAV file after successful processing
        # This ensures backup happens regardless of how the file is processed
        if wav_path.exists() and wav_path.suffix.lower() == ".wav":
            try:
                # Get MP3 name from processing state (handles renamed files)
                mp3_name = get_mp3_name_for_wav_backup(wav_path)
                if mp3_name:
                    # Try to find MP3 path
                    from transcriptx.core.utils.paths import RECORDINGS_DIR

                    recordings_dir = Path(RECORDINGS_DIR)
                    mp3_path = recordings_dir / f"{mp3_name}.mp3"
                    if not mp3_path.exists():
                        mp3_path = None
                else:
                    mp3_path = None

                # Backup WAV file (don't delete original - user will be prompted later)
                backup_path = backup_wav_after_processing(
                    wav_path,
                    mp3_path=mp3_path,
                    target_name=None,
                    delete_original=False,  # Keep original, user will decide later
                    file_entity_id=file_entity_id,
                    pipeline_run_id=result["pipeline_run_id"],
                )
                if backup_path:
                    logger.info(
                        f"Automatically backed up {wav_path.name} to {backup_path.name}"
                    )
            except Exception as backup_error:
                # Don't fail processing if backup fails
                log_error(
                    "WAV_BACKUP",
                    f"Failed to automatically backup {wav_path.name}: {backup_error}",
                    exception=backup_error,
                )
                logger.warning(
                    f"Warning: Could not backup WAV file {wav_path.name}, but processing completed successfully"
                )

    except Exception as e:
        log_error(
            "FILE_PROCESSOR",
            f"Unexpected error processing {wav_path}: {e}",
            exception=e,
        )
        result["status"] = "error"
        result["error"] = str(e)
        # Determine mp3_path from steps if available
        mp3_path_from_steps = None
        if "convert" in result.get("steps", {}):
            convert_step = result["steps"]["convert"]
            if convert_step.get("status") == "success":
                mp3_path_from_steps = convert_step.get("mp3_path")

        mark_file_processed(
            wav_path,
            {
                "status": "error",
                "error": str(e),
                "mp3_path": mp3_path_from_steps,  # Include if conversion succeeded, otherwise None
                "transcript_path": None,  # Explicitly set to None for error
                **result.get("steps", {}),
            },
        )

    return result
