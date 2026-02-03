"""
Transcript Service for TranscriptX.

This module provides a service layer for loading and caching transcript data,
eliminating redundant file reads and providing a clean interface for transcript access.

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
from transcriptx.core.utils.path_utils import (
    get_canonical_base_name,
    get_transcript_dir,
)
from transcriptx.core.utils.validation import normalize_segment_speakers
from transcriptx.io.transcript_loader import load_segments, load_transcript

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
        auto_import: Optional[bool] = None,
        strict_db: Optional[bool] = None,
        use_db: bool = False,
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
            This service only handles JSON files. VTT files should be converted
            to JSON via transcript_importer.ensure_json_artifact() first.
        """
        # Check cache
        if use_cache and self.enable_cache and transcript_path in self._segments_cache:
            cached_segments, cached_time, cached_hash = self._segments_cache[
                transcript_path
            ]
            if self._is_cache_valid(transcript_path, cached_hash):
                logger.debug(f"Using cached segments for {transcript_path}")
                normalize_segment_speakers(cached_segments)
                return cached_segments

        # Attempt DB load only if explicitly requested
        db_strict = strict_db
        if use_db:
            try:
                segments = self._load_segments_from_db(
                    transcript_path,
                    auto_import=bool(auto_import),
                    strict_db=bool(db_strict),
                )
                if segments:
                    normalize_segment_speakers(segments)
                    return segments
            except Exception as e:
                logger.warning(f"DB transcript load failed, falling back to JSON: {e}")
                if db_strict:
                    raise

        if not os.path.exists(transcript_path):
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        # Ensure we're only handling JSON files
        path_obj = Path(transcript_path)
        if path_obj.suffix.lower() != ".json":
            raise ValueError(
                f"TranscriptService only handles JSON files, got: {path_obj.suffix}. "
                f"VTT files should be converted to JSON via transcript_importer.ensure_json_artifact() first."
            )

        # Load from file
        segments = load_segments(transcript_path)
        normalize_segment_speakers(segments)

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

    def _load_segments_from_db(
        self, transcript_path: str, auto_import: bool, strict_db: bool
    ) -> List[Dict[str, Any]]:
        try:
            from transcriptx.database.transcript_adapter import TranscriptDbAdapter
            from transcriptx.database.transcript_ingestion import (
                TranscriptIngestionService,
            )

            adapter = TranscriptDbAdapter()
            try:
                return adapter.load_segments_by_path(
                    str(Path(transcript_path).resolve())
                )
            except FileNotFoundError:
                if not auto_import:
                    if strict_db:
                        raise
                    return []
                ingestion = TranscriptIngestionService()
                try:
                    ingestion.ingest_transcript(transcript_path, store_segments=True)
                finally:
                    ingestion.close()
                return adapter.load_segments_by_path(
                    str(Path(transcript_path).resolve())
                )
            finally:
                adapter.close()
        except Exception:
            if strict_db:
                raise
            return []

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
        skip_speaker_mapping: bool = False,
        batch_mode: bool = False,
        use_cache: bool = True,
        auto_import: Optional[bool] = None,
        strict_db: Optional[bool] = None,
        use_db: bool = False,
        output_dir: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], str, str, Dict[str, str]]:
        """
        Load complete transcript data with segments, paths, and speaker map.

        This is the main entry point for loading transcript data, providing
        a unified interface that combines segment loading, path resolution,
        and speaker mapping.

        Args:
            transcript_path: Path to the transcript JSON file
            skip_speaker_mapping: Skip speaker mapping if already done (default: False)
            batch_mode: Whether running in batch mode (default: False)
            use_cache: Whether to use cache if available (default: True)

        Returns:
            Tuple containing:
            - segments: List of transcript segments
            - base_name: Base name for file naming
            - transcript_dir: Output directory path
            - speaker_map: Speaker ID to name mapping

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
            auto_import=auto_import,
            strict_db=strict_db,
            use_db=use_db,
        )
        if not segments:
            raise ValueError(f"No segments found in transcript: {transcript_path}")

        # Get standardized paths
        base_name = get_canonical_base_name(transcript_path)
        transcript_dir = output_dir or get_transcript_dir(transcript_path)

        # Extract speaker information from segments (speaker_map files are deprecated)
        from transcriptx.core.utils.speaker_extraction import get_unique_speakers

        speaker_map = get_unique_speakers(segments)

        logger.debug(
            f"Loaded transcript data: {len(segments)} segments, "
            f"{len(speaker_map)} speakers from {transcript_path} "
            f"(extracted from segments)"
        )

        return segments, base_name, transcript_dir, speaker_map

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
