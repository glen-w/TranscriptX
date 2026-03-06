"""
Legacy adapters and compatibility shims.

Transitional glue code during migration. Each shim should have a TODO
indicating the target extraction. Remove as workflows are fully extracted.

- Return value adapters: convert loose dict returns to typed request/result objects
- Import shims: thin wrappers for cli/ helpers not yet extracted
"""

from __future__ import annotations

from typing import Optional


# TODO: Extract get_current_transcript_path_from_state to core/utils or
# database layer. Used after speaker mapping renames.
def get_current_transcript_path_from_state(transcript_path: str) -> Optional[str]:
    """Resolve current path after rename (e.g. speaker mapping)."""
    from transcriptx.cli.processing_state import (  # noqa: PLC0415
        get_current_transcript_path_from_state as _impl,
    )

    return _impl(transcript_path)


# TODO: Extract discover_all_transcript_paths to core/utils. Pure discovery logic.
def discover_all_transcript_paths(root=None):
    """Discover transcript JSON paths."""
    from transcriptx.cli.file_selection_utils import (  # noqa: PLC0415
        discover_all_transcript_paths as _impl,
    )

    return _impl(root)


# TODO: Extract to core/utils/speaker_extraction or analysis_utils.
def named_speaker_count_for_path(path) -> int:
    """Return named speaker count for a transcript."""
    from transcriptx.cli.analysis_utils import (  # noqa: PLC0415
        _named_speaker_count_for_path as _impl,
    )

    return _impl(path)
