"""Date-prefix helpers for rename prompts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from transcriptx.core.utils.logger import get_logger, log_error

logger = get_logger()


def extract_date_prefix_from_filename(filename: str) -> str:
    """Extract date prefix (YYMMDD_) from filename."""
    try:
        stem = Path(filename).stem
        if len(stem) >= 8 and stem[:8].isdigit():
            year = stem[:4]
            month = stem[4:6]
            day = stem[6:8]
            if int(month) in range(1, 13) and int(day) in range(1, 32):
                return f"{year[2:4]}{month}{day}_"
        if len(stem) >= 6 and stem[:6].isdigit():
            yy, mm, dd = stem[:2], stem[2:4], stem[4:6]
            if int(mm) in range(1, 13) and int(dd) in range(1, 32):
                return f"{yy}{mm}{dd}_"
        return ""
    except (ValueError, IndexError):
        return ""


def extract_date_prefix(audio_file_path: Path) -> str:
    """Extract date prefix (YYMMDD_) from audio file name or mtime."""
    try:
        date_prefix = extract_date_prefix_from_filename(audio_file_path.name)
        if date_prefix:
            return date_prefix
        if not audio_file_path.exists():
            logger.warning("Audio file not found: %s", audio_file_path)
            return ""
        mtime = audio_file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%y%m%d_")
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from {audio_file_path}: {e}",
            exception=e,
        )
        return ""


def extract_date_prefix_from_transcript(transcript_path: str | Path) -> str:
    """Extract date prefix (YYMMDD_) from transcript filename or mtime."""
    try:
        transcript_file = Path(transcript_path)
        date_prefix = extract_date_prefix_from_filename(transcript_file.name)
        if date_prefix:
            return date_prefix
        if not transcript_file.exists():
            logger.info(
                "Transcript file not found for date extraction: %s", transcript_path
            )
            return ""
        mtime = transcript_file.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%y%m%d_")
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from transcript {transcript_path}: {e}",
            exception=e,
        )
        return ""
