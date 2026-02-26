"""
Blessed entry point for loading transcript segments.

Use this module for new code that needs segments. It delegates to
TranscriptService (when cache or DB is needed) or io.load_segments (one-off).
"""

from pathlib import Path
from typing import Any, List, Optional, Union


def get_segments(
    target: Union[str, Path],
    *,
    cache: bool = True,
    use_db: bool = False,
) -> List[dict]:
    """
    Load segments for a transcript. Preferred API for new code.

    Args:
        target: Transcript file path (str or Path).
        cache: Use in-memory cache when available (default True).
        use_db: If True, try loading from database first when applicable.

    Returns:
        List of segment dicts.

    Example:
        from transcriptx.core.segments import get_segments
        segments = get_segments("/path/to/transcript.json", cache=True)
    """
    path = str(Path(target).resolve()) if target else ""
    if not path:
        return []

    if cache or use_db:
        from transcriptx.io import get_transcript_service

        service = get_transcript_service()
        return service.load_segments(
            path,
            use_cache=cache,
            use_db=use_db,
        )

    from transcriptx.io import load_segments

    return load_segments(path)
