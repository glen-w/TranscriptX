from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.path_utils import get_transcript_dir
from transcriptx.database.segment_storage import store_transcript_segments_from_json

logger = get_logger()


@dataclass
class StoreResult:
    attempted: bool
    stored: bool
    reason: str
    error_type: Optional[str] = None


def store_transcript_after_speaker_identification(
    transcript_path: str,
    audio_file_path: Optional[str] = None,
    update_existing: bool = True,
) -> StoreResult:
    """
    Store transcript segments after speaker identification (policy wrapper).

    Call sites must gate on a truthy speaker_map (no content heuristics here).
    """
    config = get_config()
    if not hasattr(config, "database") or not config.database.enabled:
        return StoreResult(attempted=False, stored=False, reason="disabled")
    if not config.database.auto_store_segments:
        return StoreResult(attempted=False, stored=False, reason="disabled")

    transcript_path_obj = Path(transcript_path)
    if not transcript_path_obj.exists():
        return StoreResult(attempted=False, stored=False, reason="missing_transcript")

    try:
        result = store_transcript_segments_from_json(
            transcript_path=str(transcript_path_obj),
            audio_file_path=audio_file_path,
            update_existing=update_existing,
        )
        if not result:
            _write_store_error(
                transcript_path_obj, RuntimeError("store_transcript_failed")
            )
            return StoreResult(
                attempted=True, stored=False, reason="store_failed", error_type=None
            )
        return StoreResult(attempted=True, stored=True, reason="ok")
    except Exception as exc:
        _write_store_error(transcript_path_obj, exc)
        logger.warning(
            "⚠️ Failed to store transcript segments: %s (%s)",
            transcript_path_obj,
            exc.__class__.__name__,
        )
        return StoreResult(
            attempted=True,
            stored=False,
            reason="exception",
            error_type=exc.__class__.__name__,
        )


def _write_store_error(transcript_path: Path, error: Exception) -> None:
    """Write last DB store error into .transcriptx folder."""
    try:
        transcript_dir = Path(get_transcript_dir(str(transcript_path)))
        error_path = transcript_dir / ".transcriptx" / "db_store_last_error.json"
        payload = {
            "transcript_path": str(transcript_path),
            "error_type": error.__class__.__name__,
            "message": str(error),
        }
        write_json(error_path, payload, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning(
            "⚠️ Failed to write db_store_last_error.json: %s (%s)",
            exc,
            exc.__class__.__name__,
        )
