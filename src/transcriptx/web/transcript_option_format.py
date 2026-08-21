"""
Shared transcript option formatting for dropdowns across web pages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptx.core.utils.analysis_picker_status import format_with_analysis_status


def decorate_transcript_picker_label(
    name: str,
    *,
    path: str | Path | None = None,
    slug: str | None = None,
) -> str:
    """Append ``(no analysis|partial analysis|analysis complete)`` to a picker name."""
    from transcriptx.web.cache_helpers import get_cached_analysis_picker_status

    status = get_cached_analysis_picker_status().status_for(path=path, slug=slug)
    return format_with_analysis_status(name, status)


def format_transcript_option_with_analysis_status(name: str, status: str) -> str:
    """Render ``Name (status)`` for transcript pickers."""
    return format_with_analysis_status(name, status)


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
