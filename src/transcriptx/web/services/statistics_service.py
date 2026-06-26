"""
Statistics service for TranscriptX web interface.

This service handles calculation of session and aggregate statistics.
"""

from datetime import datetime
from typing import Any, Dict

from pathlib import Path

from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.module_registry import get_analysis_modules, get_total_module_count
from transcriptx.web.services.file_service import FileService
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.io.metadata_display_options import get_metadata_config
from transcriptx.io.metadata_stats import (
    duration_seconds_from_document,
    word_count_from_document,
)

logger = get_logger()


def _session_from_listing(session_name: str) -> dict[str, Any] | None:
    for session in cached_list_available_sessions():
        if session.get("name") == session_name:
            return session
    return None


class StatisticsService:
    """Service for calculating statistics."""

    @staticmethod
    def get_session_statistics(session_name: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a session.

        Args:
            session_name: Name of the session

        Returns:
            Dictionary with session statistics
        """
        stats = {
            "duration_seconds": 0,
            "speaker_count": 0,
            "word_count": 0,
            "segment_count": 0,
            "last_updated": None,
            "analysis_completion": 0,
        }

        listing_entry = _session_from_listing(session_name)
        if listing_entry is not None:
            stats["segment_count"] = int(listing_entry.get("segment_count", 0))
            stats["duration_seconds"] = float(listing_entry.get("duration_seconds", 0))
            stats["speaker_count"] = int(listing_entry.get("speaker_count", 0))
            stats["word_count"] = int(listing_entry.get("word_count", 0))
        else:
            transcript_data = FileService.load_transcript_by_session(session_name)
            if transcript_data:
                meta_cfg = get_metadata_config()
                stats["segment_count"] = len(transcript_data.get("segments", []))
                stats["duration_seconds"] = duration_seconds_from_document(
                    transcript_data,
                    method=meta_cfg.duration_calculation,
                )
                speakers = {
                    seg.get("speaker")
                    for seg in transcript_data.get("segments", [])
                    if isinstance(seg, dict) and seg.get("speaker")
                }
                stats["speaker_count"] = len(speakers)
                stats["word_count"] = word_count_from_document(
                    transcript_data,
                    allow_segment_fallback=True,
                    allow_legacy_words_alias=meta_cfg.legacy_words_alias,
                )

        modules = get_analysis_modules(session_name)
        total_modules = get_total_module_count()
        stats["analysis_completion"] = (
            int((len(modules) / total_modules) * 100) if total_modules > 0 else 0
        )

        session_dir = Path(OUTPUTS_DIR) / session_name
        if session_dir.exists():
            try:
                mtime = session_dir.stat().st_mtime
                stats["last_updated"] = datetime.fromtimestamp(mtime).isoformat()
            except Exception:
                pass

        return stats

    @staticmethod
    def get_all_sessions_statistics() -> Dict[str, Any]:
        """
        Get aggregate statistics across all sessions.

        Returns:
            Dictionary with aggregate statistics
        """
        sessions = cached_list_available_sessions()

        if not sessions:
            return {
                "total_sessions": 0,
                "total_duration_seconds": 0,
                "total_duration_minutes": 0,
                "total_duration_hours": 0.0,
                "total_word_count": 0,
                "total_speakers": 0,
                "average_completion": 0,
            }

        total_duration = sum(s.get("duration_seconds", 0) for s in sessions)
        total_words = sum(s.get("word_count", 0) for s in sessions)
        completion_rates = [s.get("analysis_completion", 0) for s in sessions]

        total_speakers = (
            max(s.get("speaker_count", 0) for s in sessions) if sessions else 0
        )

        return {
            "total_sessions": len(sessions),
            "total_duration_seconds": total_duration,
            "total_duration_minutes": round(total_duration / 60, 1),
            "total_duration_hours": round(total_duration / 3600, 2),
            "total_word_count": total_words,
            "total_speakers": total_speakers,
            "average_completion": (
                round(sum(completion_rates) / len(completion_rates), 1)
                if completion_rates
                else 0
            ),
            "recent_sessions": (
                len([s for s in sessions if s.get("last_updated")]) if sessions else 0
            ),
        }
