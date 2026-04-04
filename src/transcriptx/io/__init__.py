"""
Centralized I/O operations for TranscriptX.

This module provides a unified interface for all file I/O operations,
transcript loading, speaker mapping, and data serialization across
the TranscriptX codebase.

Key Features:
- Standardized transcript loading with validation
- Unified speaker mapping operations
- Consistent file I/O patterns
- Error handling and validation
- Support for multiple data formats
- Caching service for efficient data access

Usage:
    from transcriptx.io import (
        load_segments,
        load_transcript,
        load_transcript_data,
        save_json,
        save_csv,
        TranscriptService,
        get_transcript_service,
    )

``load_transcript_data`` delegates to ``get_transcript_service().load_transcript_data``.
"""

from .transcript_loader import (
    TranscriptLoadResult,
    load_segments,
    load_transcript,
)
from .file_io import (
    save_json,
    save_csv,
    save_transcript,
)
from .transcript_service import (
    TranscriptService,
    get_transcript_service,
    reset_transcript_service,
)


def load_transcript_data(
    transcript_path: str,
    batch_mode: bool = False,
):
    """Load transcript via the default ``TranscriptService`` (convenience wrapper)."""
    return get_transcript_service().load_transcript_data(
        transcript_path,
        batch_mode=batch_mode,
    )


__all__ = [
    # Transcript loading
    "TranscriptLoadResult",
    "load_segments",
    "load_transcript",
    "load_transcript_data",
    # File I/O
    "save_json",
    "save_csv",
    "save_transcript",
    # Service layer
    "TranscriptService",
    "get_transcript_service",
    "reset_transcript_service",
]
