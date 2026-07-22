"""
Data access utilities for TranscriptX web interface.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver
from transcriptx.web.services.file_service import FileService
from transcriptx.web.services.statistics_service import StatisticsService
from transcriptx.web.services.summary_service import SummaryService

logger = get_logger()


def get_session_statistics(session_name: str) -> Dict[str, Any]:
    return StatisticsService.get_session_statistics(session_name)


def list_available_sessions() -> List[Dict[str, Any]]:
    from transcriptx.web.cache_helpers import cached_list_available_sessions

    return cached_list_available_sessions()


def load_transcript_by_session(session_name: str) -> Optional[Dict[str, Any]]:
    return FileService.load_transcript_by_session(session_name)


def load_transcript_with_path_by_session(
    session_name: str,
) -> Optional[tuple[Dict[str, Any], Path]]:
    """Load transcript data together with the canonical path that was read."""
    return FileService.load_transcript_with_path_by_session(session_name)


def get_analysis_modules(session_name: str) -> List[str]:
    from transcriptx.web.module_registry import get_analysis_modules

    return get_analysis_modules(session_name)


def load_analysis_data(session_name: str, module_name: str) -> Optional[Dict[str, Any]]:
    return FileService.load_analysis_data(session_name, module_name)


def list_charts(session_name: str, module_name: str) -> List[Dict[str, str]]:
    return FileService.list_charts(session_name, module_name)


def get_all_sessions_statistics() -> Dict[str, Any]:
    return StatisticsService.get_all_sessions_statistics()


def extract_analysis_summary(
    module_name: str, analysis_data: Dict[str, Any]
) -> Dict[str, Any]:
    return SummaryService.extract_analysis_summary(module_name, analysis_data)


def resolve_speaker_names_from_sidecars(
    segments: List[Dict[str, Any]], transcript_path: str
) -> List[Dict[str, Any]]:
    try:
        # Web viewer often passes a session id like "<slug>/<run_id>" here.
        # Speaker map sidecars live beside the *transcript file*, so we need to
        # resolve that session id to a real path first.
        resolved_path: Path
        candidate = Path(transcript_path)
        if candidate.exists():
            resolved_path = candidate
        else:
            from_session = FileService.resolve_transcript_path(transcript_path)
            resolved_path = from_session or candidate

        resolver = SpeakerMapResolver()
        state = resolver.load_mapping(resolved_path)
        resolved_segments = resolver.resolve_segments(segments, state)
        for segment in resolved_segments:
            speaker = segment.get("speaker")
            if speaker and not segment.get("speaker_display"):
                segment["speaker_display"] = str(speaker)
        return resolved_segments
    except Exception as exc:
        logger.warning("Failed to resolve speaker names from sidecars: %s", exc)
        resolved_segments: List[Dict[str, Any]] = []
        for segment in segments:
            copied = dict(segment)
            speaker = copied.get("speaker")
            if speaker and not copied.get("speaker_display"):
                copied["speaker_display"] = str(speaker)
            resolved_segments.append(copied)
        return resolved_segments


resolve_speaker_names_from_db = resolve_speaker_names_from_sidecars
