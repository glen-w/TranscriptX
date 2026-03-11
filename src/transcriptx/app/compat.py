"""
Legacy adapters and compatibility shims.

Transitional glue code during migration. These now delegate to their
canonical locations in core/ rather than the removed cli/ package.
"""

from __future__ import annotations

from typing import Optional


def get_current_transcript_path_from_state(transcript_path: str) -> Optional[str]:
    """Resolve current path after rename (e.g. speaker mapping)."""
    from transcriptx.core.utils.processing_state import (  # noqa: PLC0415
        get_current_transcript_path_from_state as _impl,
    )

    return _impl(transcript_path)


def discover_all_transcript_paths(root=None):
    """Discover transcript JSON paths."""
    from transcriptx.core.utils.file_discovery import (  # noqa: PLC0415
        discover_all_transcript_paths as _impl,
    )

    return _impl(root)


def named_speaker_count_for_path(path) -> int:
    """Return named speaker count for a transcript."""
    from transcriptx.core.utils.speaker_extraction import (  # noqa: PLC0415
        named_speaker_count_for_path as _impl,
    )

    return _impl(path)
