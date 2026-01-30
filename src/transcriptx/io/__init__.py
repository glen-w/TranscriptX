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
        load_speaker_map,
        save_json,
        save_csv,
        TranscriptService,
        get_transcript_service,
    )
"""

from .transcript_loader import (
    load_segments,
    load_transcript,
    load_transcript_data,
)
from .speaker_mapping import (
    build_speaker_map,
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

__all__ = [
    # Transcript loading
    "load_segments",
    "load_transcript",
    "load_transcript_data",
    # Speaker mapping
    "build_speaker_map",
    # File I/O
    "save_json",
    "save_csv",
    "save_transcript",
    # Service layer
    "TranscriptService",
    "get_transcript_service",
    "reset_transcript_service",
]
