"""
Statistics service for TranscriptX web interface.

This service handles calculation of session and aggregate statistics.
"""

from datetime import datetime
import json
from typing import Any, Dict

from pathlib import Path

from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.module_registry import get_analysis_modules, get_total_module_count
from transcriptx.web.services.file_service import FileService
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR, OUTPUTS_DIR
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


def _transcript_identity(session: dict[str, Any]) -> str:
    """Stable key for unique-transcript aggregation (one row per source transcript)."""
    for field in ("transcript_key", "slug"):
        value = session.get(field)
        if value:
            return str(value)
    name = session.get("name")
    if name:
        return str(name).split("/", 1)[0]
    return str(id(session))


def _unique_transcripts(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Collapse run-level sessions to one entry per transcript.

    Listing is newest-first; keep the first (most recent) run per transcript so
    duration/words are not double-counted across re-analyses.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for session in sessions:
        key = _transcript_identity(session)
        if key in seen:
            continue
        seen.add(key)
        unique.append(session)
    return unique


def _manifest_artifact_bytes(run_dir: Path) -> int:
    """Sum declared artifact sizes from a run's ``manifest.json`` (0 if missing)."""
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return 0
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        return 0
    total = 0
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        try:
            total += int(item.get("bytes") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _total_artifact_bytes(sessions: list[dict[str, Any]]) -> int:
    """
    Total produced-artifact bytes across all transcript sessions and group runs.

    Uses each run's own artifact manifest (no group-member merge) so on-disk
    outputs are counted once.
    """
    total = 0
    for session in sessions:
        path = session.get("path")
        if not path:
            continue
        try:
            total += _manifest_artifact_bytes(Path(path))
        except Exception:
            continue

    group_root = Path(GROUP_OUTPUTS_DIR)
    if not group_root.is_dir():
        return total
    try:
        group_dirs = list(group_root.iterdir())
    except OSError:
        return total
    for group_dir in group_dirs:
        if not group_dir.is_dir() or group_dir.name.startswith("."):
            continue
        try:
            run_dirs = list(group_dir.iterdir())
        except OSError:
            continue
        for run_dir in run_dirs:
            if not run_dir.is_dir() or run_dir.name.startswith("."):
                continue
            try:
                total += _manifest_artifact_bytes(run_dir)
            except Exception:
                continue
    return total


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
        Get aggregate statistics across unique transcripts.

        Multiple analysis runs for the same transcript count once (duration,
        words, speakers, and completion use the most recent run per transcript).
        Artifact size sums every transcript session plus group runs.

        Returns:
            Dictionary with aggregate statistics
        """
        sessions = cached_list_available_sessions()
        transcripts = _unique_transcripts(sessions)
        total_artifact_bytes = _total_artifact_bytes(sessions)

        if not transcripts:
            return {
                "total_transcripts": 0,
                "total_sessions": 0,
                "total_duration_seconds": 0,
                "total_duration_minutes": 0,
                "total_duration_hours": 0.0,
                "total_word_count": 0,
                "total_speakers": 0,
                "average_completion": 0,
                "total_artifact_bytes": total_artifact_bytes,
            }

        total_duration = sum(s.get("duration_seconds", 0) for s in transcripts)
        total_words = sum(s.get("word_count", 0) for s in transcripts)
        completion_rates = [s.get("analysis_completion", 0) for s in transcripts]

        total_speakers = max(s.get("speaker_count", 0) for s in transcripts)

        return {
            "total_transcripts": len(transcripts),
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
            "recent_sessions": len([s for s in transcripts if s.get("last_updated")]),
            "total_artifact_bytes": total_artifact_bytes,
        }
