"""
Statistics service for TranscriptX web interface.

This service handles calculation of session and aggregate statistics.
"""

from datetime import datetime
from typing import Any, Dict

from transcriptx.web.module_registry import get_analysis_modules, get_total_module_count
from transcriptx.web.services.file_service import FileService
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


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

        # Load transcript to get basic stats
        transcript_data = FileService.load_transcript_data(session_name)
        if transcript_data:
            segments = transcript_data.get("segments", [])
            stats["segment_count"] = len(segments)

            # Calculate duration
            if segments:
                stats["duration_seconds"] = max(
                    seg.get("end", 0) for seg in segments
                ) - min(seg.get("start", 0) for seg in segments)

            # Count speakers
            speakers = set(seg.get("speaker") for seg in segments if seg.get("speaker"))
            stats["speaker_count"] = len(speakers)

            # Count words
            stats["word_count"] = sum(
                len(seg.get("text", "").split()) for seg in segments
            )

        # Get analysis modules
        modules = get_analysis_modules(session_name)
        total_modules = (
            get_total_module_count()
        )  # Use dynamic count instead of magic number
        stats["analysis_completion"] = (
            int((len(modules) / total_modules) * 100) if total_modules > 0 else 0
        )

        # Get last updated time from directory
        session_dir = FileService._resolve_session_dir(session_name)
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
        # Import here to avoid circular dependency
        sessions = FileService.list_available_sessions()

        if not sessions:
            return {
                "total_sessions": 0,
                "total_duration_minutes": 0,
                "total_duration_hours": 0.0,
                "total_word_count": 0,
                "total_speakers": 0,
                "average_completion": 0,
            }

        total_duration = sum(s.get("duration_seconds", 0) for s in sessions)
        total_words = sum(s.get("word_count", 0) for s in sessions)
        completion_rates = [s.get("analysis_completion", 0) for s in sessions]

        # Count unique speakers (simplified - would need to load all transcripts for accurate count)
        total_speakers = (
            max(s.get("speaker_count", 0) for s in sessions) if sessions else 0
        )

        return {
            "total_sessions": len(sessions),
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
