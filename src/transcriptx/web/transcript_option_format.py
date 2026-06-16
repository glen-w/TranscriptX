"""
Shared transcript option formatting for dropdowns across web pages.
"""

from __future__ import annotations

from typing import Any


def format_transcript_option_with_speaker_status(summary: Any) -> str:
    """
    Format a transcript summary label with speaker-identification status.

    Expected attrs on ``summary``:
    - base_name
    - speaker_map_status
    - segment_count
    - unidentified_speaker_count
    - ignored_speaker_count
    """
    base_name = str(getattr(summary, "base_name", "") or "")
    status = str(getattr(summary, "speaker_map_status", "none") or "none")
    seg_count = int(getattr(summary, "segment_count", 0) or 0)
    base = f"{base_name} ({status}, {seg_count} segs)"
    if status != "partial":
        return base

    unidentified = int(getattr(summary, "unidentified_speaker_count", 0) or 0)
    ignored = int(getattr(summary, "ignored_speaker_count", 0) or 0)
    return f"{base}, {unidentified} unidentified, {ignored} ignored"
