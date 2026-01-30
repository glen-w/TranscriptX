"""
Utilities for maintaining performance span integrity.

This module provides functions to detect and mark abandoned performance spans.
Abandoned spans are those that were started but never completed (missing end_time),
typically due to process crashes, kills, or timeouts.
"""

from datetime import datetime, timedelta
from typing import Optional

from transcriptx.database import get_session
from transcriptx.database.repositories import PerformanceSpanRepository


def cleanup_stale_spans(
    max_age: timedelta,
    status_message: str = "abandoned/crashed",
    now: Optional[datetime] = None,
) -> int:
    """
    Mark spans with missing end_time older than max_age as ERROR.

    This function identifies spans that were started but never completed,
    which typically indicates a process crash, kill, or timeout. These spans
    are marked as ERROR with the provided status message.

    Args:
        max_age: Maximum age for a span to be considered stale. Spans older
                 than this with no end_time will be marked as abandoned.
        status_message: Message to set on abandoned spans (default: "abandoned/crashed")
        now: Current time (for testing). Defaults to datetime.utcnow()

    Returns:
        Number of spans marked as abandoned.

    Example:
        # Mark spans older than 24 hours as abandoned
        count = cleanup_stale_spans(timedelta(hours=24))
        print(f"Marked {count} spans as abandoned")
    """
    cutoff_time = (now or datetime.utcnow()) - max_age
    session = get_session()
    try:
        repo = PerformanceSpanRepository(session)
        return repo.mark_stale_spans(
            cutoff_time=cutoff_time, status_message=status_message
        )
    finally:
        session.close()


def cleanup_abandoned_transcription_spans(
    max_age_hours: int = 24,
    status_message: str = "abandoned/crashed",
) -> int:
    """
    Convenience function to clean up abandoned transcription spans.

    This is a specialized version of cleanup_stale_spans with a default
    24-hour threshold, which is appropriate for transcription operations
    that should typically complete within a few hours.

    Args:
        max_age_hours: Maximum age in hours (default: 24)
        status_message: Message to set on abandoned spans

    Returns:
        Number of spans marked as abandoned.
    """
    return cleanup_stale_spans(
        max_age=timedelta(hours=max_age_hours),
        status_message=status_message,
    )
