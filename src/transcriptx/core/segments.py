"""
Blessed entry point for loading transcript segments.

Use this module for new code that needs segments. It delegates to
TranscriptService (when caching is enabled) or io.load_segments (one-off).
"""

from pathlib import Path
from typing import List, Union


def get_segments(
    target: Union[str, Path],
    *,
    cache: bool = True,
) -> List[dict]:
    """
    Load segments for a transcript. Preferred API for new code.

    Args:
        target: Transcript file path (str or Path).
        cache: Use in-memory cache when available (default True).

    Returns:
        List of segment dicts.

    Example:
        from transcriptx.core.segments import get_segments
        segments = get_segments("/path/to/transcript.json", cache=True)
    """
    path = str(Path(target).resolve()) if target else ""
    if not path:
        return []

    if cache:
        from transcriptx.io import get_transcript_service

        service = get_transcript_service()
        return service.load_segments(
            path,
            use_cache=cache,
        )

    from transcriptx.io import load_segments

    return load_segments(path)
