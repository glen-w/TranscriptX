"""
Transcript Service for TranscriptX.

This module provides a service layer for loading and caching transcript data,
eliminating redundant file reads and providing a clean interface for transcript access.

Relationship to the ingestion pipeline
---------------------------------------
``TranscriptService`` operates on already-imported schema v1.0 JSON artifacts.
It does not import or convert raw source files itself.  Callers that hold a path
to a non-JSON file (VTT, SRT, Otter JSON, Sembly HTML, etc.) should normalise it
first with ``transcript_importer.ensure_json_artifact(path)`` — which runs the
adapter detection pipeline and returns a path to the canonical JSON — then pass
that JSON path to this service.  This keeps the service layer source-format-agnostic.

Path resolution invariant: All file-path resolution for transcripts is owned by this
layer (and transcript_loader / _path_resolution). If the input path exists, it is used;
if missing, resolution is attempted via _path_resolution.resolve_file_path (e.g. renamed
files after speaker mapping). If still missing, FileNotFoundError is raised with the
original path. No caller outside the io layer should implement its own path-resolution
fallback.

Key Features:
- Transcript loading with caching
- Speaker map loading with caching
- Cache invalidation on file modification
- Thread-safe operations
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils._path_core import (
    get_canonical_base_name,
    get_transcript_dir,
)
from transcriptx.io.transcript_loader import (
    TranscriptLoadResult,
    load_segments,
    load_transcript,
)

logger = get_logger()


class TranscriptService:
    """
    Service for loading and caching transcript data.

    This service provides a unified interface for transcript loading with
    built-in caching to avoid redundant file reads during pipeline execution.
    """

    def __init__(self, enable_cache: bool = True):
        """
        Initialize the transcript service.

        Args:
            enable_cache: Whether to enable caching (default: True)
        """
        self.enable_cache = enable_cache
        self._transcript_cache: Dict[str, Tuple[Any, float, str]] = {}
        self._speaker_map_cache: Dict[str, Tuple[Dict[str, str], float]] = {}
        self._segments_cache: Dict[str, Tuple[List[Dict[str, Any]], float, str]] = {}

    def _get_file_hash(self, file_path: str) -> str:
        """Get hash of file for cache invalidation."""
        try:
            stat = os.stat(file_path)
            # Use modification time and size for quick hash
            return f"{stat.st_mtime}_{stat.st_size}"
        except OSError:
            return ""

    def _is_cache_valid(self, file_path: str, cached_hash: str) -> bool:
        """Check if cached data is still valid."""
        if not self.enable_cache:
            return False
        current_hash = self._get_file_hash(file_path)
        return current_hash == cached_hash and current_hash != ""

    def load_segments(
        self,
        transcript_path: str,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Load segments from a transcript file with optional caching.

        Args:
            transcript_path: Path to the transcript JSON file
            use_cache: Whether to use cache if available (default: True)

        Returns:
            List of transcript segments

        Raises:
            FileNotFoundError: If transcript file doesn't exist
            ValueError: If transcript file is invalid or not JSON

        Note:
            This service only accepts JSON artifacts in schema v1.0 format.
            Any other source format (VTT, SRT, Otter, Sembly, plain text, etc.)
            must be converted first with
            ``transcript_importer.ensure_json_artifact(path)``, which runs the
            adapter detection pipeline and produces a canonical JSON file.
            The resulting path can then be passed here.
        """
        # Check cache
        if use_cache and self.enable_cache and transcript_path in self._segments_cache:
            cached_segments, cached_time, cached_hash = self._segments_cache[
                transcript_path
            ]
            if self._is_cache_valid(transcript_path, cached_hash):
                logger.debug(f"Using cached segments for {transcript_path}")
                return cached_segments

        if not os.path.exists(transcript_path):
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        # Ensure we're only handling JSON files
        path_obj = Path(transcript_path)
        if path_obj.suffix.lower() != ".json":
            raise ValueError(
                f"TranscriptService only accepts schema v1.0 JSON artifacts, "
                f"got: {path_obj.suffix!r}. "
                f"Convert the source file first with "
                f"transcript_importer.ensure_json_artifact(path)."
            )

        # Load from file
        segments = load_segments(transcript_path)

        # Cache the result
        if use_cache and self.enable_cache:
            file_hash = self._get_file_hash(transcript_path)
            self._segments_cache[transcript_path] = (
                segments,
                datetime.now().timestamp(),
                file_hash,
            )
            logger.debug(f"Cached segments for {transcript_path}")

        return segments

    def replace_cached_segments(
        self, transcript_path: str, segments: List[Dict[str, Any]]
    ) -> None:
        """
        Replace the in-memory segment list for a path after pipeline-side mutation
        (e.g. speaker map resolution) so later cache hits match context segments.
        """
        if not self.enable_cache:
            return
        if transcript_path not in self._segments_cache:
            return
        _old_segments, ts, file_hash = self._segments_cache[transcript_path]
        self._segments_cache[transcript_path] = (segments, ts, file_hash)

    def load_transcript(self, transcript_path: str, use_cache: bool = True) -> Any:
        """
        Load complete transcript file with optional caching.

        Args:
            transcript_path: Path to the transcript JSON file
            use_cache: Whether to use cache if available (default: True)

        Returns:
            Complete transcript data

        Raises:
            FileNotFoundError: If transcript file doesn't exist
        """
        if not os.path.exists(transcript_path):
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        # Check cache
        if (
            use_cache
            and self.enable_cache
            and transcript_path in self._transcript_cache
        ):
            cached_data, cached_time, cached_hash = self._transcript_cache[
                transcript_path
            ]
            if self._is_cache_valid(transcript_path, cached_hash):
                logger.debug(f"Using cached transcript for {transcript_path}")
                return cached_data

        # Load from file
        data = load_transcript(transcript_path)

        # Cache the result
        if use_cache and self.enable_cache:
            file_hash = self._get_file_hash(transcript_path)
            self._transcript_cache[transcript_path] = (
                data,
                datetime.now().timestamp(),
                file_hash,
            )
            logger.debug(f"Cached transcript for {transcript_path}")

        return data

    def load_transcript_data(
        self,
        transcript_path: str,
        batch_mode: bool = False,
        use_cache: bool = True,
        output_dir: Optional[str] = None,
    ) -> TranscriptLoadResult:
        """
        Load complete transcript data with segments and paths.

        This is the main entry point for loading transcript data, providing
        a unified interface that combines segment loading, path resolution,
        and speaker mapping.

        Args:
            transcript_path: Path to the transcript JSON file
            batch_mode: Whether running in batch mode (default: False)
            use_cache: Whether to use cache if available (default: True)

        Returns:
            Tuple containing:
            - segments: List of transcript segments
            - base_name: Base name for file naming
            - transcript_dir: Output directory path

        Raises:
            FileNotFoundError: If transcript file doesn't exist
            ValueError: If transcript file is invalid or empty
        """
        # Validate transcript file exists
        if not os.path.exists(transcript_path):
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        # Load segments (with caching)
        segments = self.load_segments(
            transcript_path,
            use_cache=use_cache,
        )
        if not segments:
            raise ValueError(f"No segments found in transcript: {transcript_path}")

        # Get standardized paths
        base_name = get_canonical_base_name(transcript_path)
        transcript_dir = output_dir or get_transcript_dir(transcript_path)

        # Extract speaker information from segments for logging only.
        from transcriptx.core.utils.speaker_extraction import get_unique_speakers

        speaker_map = get_unique_speakers(segments)

        logger.debug(
            f"Loaded transcript data: {len(segments)} segments, "
            f"{len(speaker_map)} speakers from {transcript_path} "
            f"(extracted from segments)"
        )

        return TranscriptLoadResult(
            segments=segments,
            base_name=base_name,
            transcript_dir=transcript_dir,
        )

    def invalidate_cache(self, transcript_path: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific transcript or all transcripts.

        Args:
            transcript_path: Path to specific transcript to invalidate,
                           or None to invalidate all caches
        """
        if transcript_path is None:
            self._transcript_cache.clear()
            self._segments_cache.clear()
            self._speaker_map_cache.clear()
            logger.debug("Cleared all transcript caches")
        else:
            # Invalidate transcript and segments cache
            self._transcript_cache.pop(transcript_path, None)
            self._segments_cache.pop(transcript_path, None)

            # Speaker map cache is no longer used

            logger.debug(f"Invalidated cache for {transcript_path}")

    def clear_cache(self) -> None:
        """Clear all caches."""
        self.invalidate_cache()


# Global service instance
_default_service: Optional[TranscriptService] = None


def get_transcript_service(enable_cache: bool = True) -> TranscriptService:
    """
    Get the default transcript service instance.

    Args:
        enable_cache: Whether to enable caching (only used on first call)

    Returns:
        TranscriptService instance
    """
    global _default_service
    if _default_service is None:
        _default_service = TranscriptService(enable_cache=enable_cache)
    return _default_service


def reset_transcript_service() -> None:
    """Reset the default transcript service (useful for testing)."""
    global _default_service
    _default_service = None
