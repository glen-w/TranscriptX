"""
Data access utilities for TranscriptX web interface.

This module provides backward-compatible functions that delegate to
the new service layer. New code should use the services directly.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from transcriptx.web.services directly.
"""

from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.web.services import FileService, StatisticsService, SummaryService

logger = get_logger()


def get_session_statistics(session_name: str) -> Dict[str, Any]:
    """
    Get comprehensive statistics for a session.

    Args:
        session_name: Name of the session

    Returns:
        Dictionary with session statistics
    """
    return StatisticsService.get_session_statistics(session_name)


def list_available_sessions() -> List[Dict[str, Any]]:
    """
    Scan data/outputs/<slug>/<run_id> for available runs.

    This function delegates to FileService to avoid circular dependencies.
    """
    return FileService.list_available_sessions()


def load_transcript_data(session_name: str) -> Optional[Dict[str, Any]]:
    """
    Load transcript from data/transcripts/ or data/outputs/{session}/.

    Args:
        session_name: Name of the session

    Returns:
        Transcript data dictionary or None if not found
    """
    return FileService.load_transcript_data(session_name)


def get_analysis_modules(session_name: str) -> List[str]:
    """
    List available analysis modules for a session.

    Args:
        session_name: Name of the session

    Returns:
        List of module names
    """
    from transcriptx.web.module_registry import get_analysis_modules

    return get_analysis_modules(session_name)


def load_analysis_data(session_name: str, module_name: str) -> Optional[Dict[str, Any]]:
    """
    Load analysis JSON data for a module.

    Args:
        session_name: Name of the session
        module_name: Name of the analysis module

    Returns:
        Analysis data dictionary or None if not found
    """
    return FileService.load_analysis_data(session_name, module_name)


def list_charts(session_name: str, module_name: str) -> List[Dict[str, str]]:
    """
    List available chart images for a module.

    Args:
        session_name: Name of the session
        module_name: Name of the analysis module

    Returns:
        List of chart dictionaries with name and path
    """
    return FileService.list_charts(session_name, module_name)


def get_all_sessions_statistics() -> Dict[str, Any]:
    """
    Get aggregate statistics across all sessions.

    Returns:
        Dictionary with aggregate statistics
    """
    return StatisticsService.get_all_sessions_statistics()


def extract_analysis_summary(
    module_name: str, analysis_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract a summary with key metrics and highlights from analysis data.

    Args:
        module_name: Name of the analysis module
        analysis_data: The analysis data dictionary

    Returns:
        Dictionary with has_data, key_metrics, and highlights
    """
    return SummaryService.extract_analysis_summary(module_name, analysis_data)


def resolve_speaker_names_from_db(
    segments: List[Dict[str, Any]], session_name: str
) -> List[Dict[str, Any]]:
    """
    Resolve speaker names from database for transcript segments.

    Primary source: Database query
    Fallback: Use names from JSON if available
    Last resort: Use speaker_map JSON file

    Args:
        segments: List of transcript segments
        session_name: Session name for fallback lookup

    Returns:
        Segments with resolved speaker names
    """
    try:
        from transcriptx.web.db_utils import resolve_speaker_name

        resolved_segments = []
        speaker_cache = {}  # Cache resolved names

        for segment in segments:
            resolved_segment = segment.copy()
            speaker_identifier = segment.get("speaker", "Unknown")

            # Try database first
            if speaker_identifier not in speaker_cache:
                # Try by database ID if available
                db_id = segment.get("speaker_db_id")
                if db_id:
                    resolved_name = resolve_speaker_name(db_id)
                else:
                    # Try by name
                    resolved_name = resolve_speaker_name(speaker_identifier)

                # Fallback to JSON name if database lookup failed
                if not resolved_name:
                    resolved_name = speaker_identifier

                speaker_cache[speaker_identifier] = resolved_name

            resolved_segment["speaker_display"] = speaker_cache[speaker_identifier]
            resolved_segments.append(resolved_segment)

        return resolved_segments

    except Exception as e:
        # If database lookup fails, return segments as-is
        logger.warning(f"Failed to resolve speaker names from database: {e}")
        return segments
