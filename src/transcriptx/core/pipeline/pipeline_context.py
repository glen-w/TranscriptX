"""
Pipeline Context for TranscriptX.

This module provides a context object that holds all data needed during
pipeline execution, eliminating redundant file reads and enabling efficient
data passing between analysis modules.

Key Features:
- Single transcript load per pipeline execution
- Cached speaker maps
- Shared analysis results
- Efficient data access
"""

from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.transcript_service import TranscriptService

logger = get_logger()


class PipelineContext:
    """
    Context object that holds all data needed during pipeline execution.

    This class eliminates redundant file reads by loading transcript data
    once and passing it through the pipeline. It also caches intermediate
    results that can be reused by multiple analysis modules.

    Lifecycle:
    1. Created when pipeline starts (in run_analysis_pipeline or DAGPipeline)
    2. Used by all analysis modules during execution
    3. Should be closed after pipeline completes (via close() or context manager)
    4. Resources are cleaned up on close() or when context is garbage collected

    Ownership:
    - Created and owned by the pipeline executor (DAGPipeline or run_analysis_pipeline)
    - Passed to analysis modules as read-only (modules should not modify context)
    - Closed by the pipeline executor after all modules complete
    """

    def __init__(
        self,
        transcript_path: str,
        speaker_map: Optional[Dict[str, str]] = None,
        skip_speaker_mapping: bool = False,
        batch_mode: bool = False,
        auto_import: bool | None = None,
        strict_db: bool | None = None,
        use_db: bool = False,
        output_dir: Optional[str] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        """
        Initialize the pipeline context.

        Args:
            transcript_path: Path to the transcript file
            skip_speaker_mapping: Skip speaker mapping if already done (deprecated, kept for compatibility)
            batch_mode: Whether running in batch mode

        Raises:
            FileNotFoundError: If transcript file doesn't exist
            ValueError: If transcript data is invalid
            RuntimeError: If context initialization fails
        """
        self.transcript_path = transcript_path
        if speaker_map is not None:
            logger.warning(
                "PipelineContext speaker_map is deprecated; speaker info now derives from segments."
            )

        # Create TranscriptService instance and load transcript data once
        self._transcript_service = TranscriptService(enable_cache=True)
        try:
            self.segments, self.base_name, self.transcript_dir, _ = (
                self._transcript_service.load_transcript_data(
                    transcript_path,
                    skip_speaker_mapping=skip_speaker_mapping,
                    batch_mode=batch_mode,
                    use_cache=True,
                    auto_import=auto_import,
                    strict_db=strict_db,
                    use_db=use_db,
                    output_dir=output_dir,
                )
            )
        except FileNotFoundError as e:
            logger.error(f"Transcript file not found: {transcript_path}")
            raise
        except ValueError as e:
            logger.error(f"Invalid transcript data: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load transcript data: {e}")
            raise RuntimeError(f"Failed to initialize PipelineContext: {e}") from e

        # Extract speaker information from segments
        # Speaker info comes directly from segments via speaker_db_id
        from transcriptx.core.utils.speaker_extraction import (
            get_unique_speakers,
            set_speaker_display_map,
        )
        from transcriptx.io.transcript_loader import extract_speaker_map_from_transcript

        self.speaker_map = get_unique_speakers(self.segments)
        logger.debug(f"Extracted {len(self.speaker_map)} speakers from segments")

        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )

        self.transcript_key = transcript_key or compute_transcript_identity_hash(
            self.segments
        )
        self.run_id = run_id
        self._speaker_map_metadata = extract_speaker_map_from_transcript(
            transcript_path
        )
        if self._speaker_map_metadata:
            set_speaker_display_map(self._speaker_map_metadata)

        # Cache for analysis results (keyed by module name)
        self._analysis_results: Dict[str, Any] = {}
        self.runtime_flags: Dict[str, Any] = {}

        # Cache for computed values that can be reused
        self._computed_values: Dict[str, Any] = {}

        # Track if context is closed
        self._closed = False

        # Track if context is frozen (read-only)
        self._frozen = False

        logger.debug(
            f"Initialized pipeline context: {len(self.segments)} segments, "
            f"{len(self.speaker_map)} speakers"
        )

    def validate(self) -> bool:
        """
        Validate that context is properly initialized.

        Returns:
            True if context is valid, False otherwise
        """
        if self._closed:
            logger.warning("PipelineContext is closed")
            return False

        if not self.segments:
            logger.warning("PipelineContext has no segments loaded")
            return False

        # Note: speaker_map is derived from segments - speaker info comes from segments

        if not self.transcript_path:
            logger.warning("PipelineContext has no transcript path")
            return False

        return True

    def close(self) -> None:
        """
        Close the context and clean up resources.

        This should be called after pipeline execution completes.
        The context can still be accessed after closing, but resources
        may be cleaned up.
        """
        if self._closed:
            return

        # Clear caches to free memory
        self._analysis_results.clear()
        self._computed_values.clear()

        # Note: TranscriptService cache is shared, so we don't clear it here
        # The service manages its own cache lifecycle

        try:
            from transcriptx.core.utils.speaker_extraction import (
                clear_speaker_display_map,
            )

            clear_speaker_display_map()
        except Exception:
            pass

        self._closed = True
        logger.debug("PipelineContext closed and resources cleaned up")

    def __enter__(self):
        """Context manager entry."""
        return self

    def freeze(self) -> None:
        """
        Freeze the context, making it read-only.

        This is useful for parallel execution where multiple modules
        should not mutate the shared context. After freezing, attempts
        to modify the context will raise RuntimeError.
        """
        self._frozen = True
        logger.debug("PipelineContext frozen (read-only)")

    def is_frozen(self) -> bool:
        """Check if context is frozen."""
        return self._frozen

    def get_segments(self) -> List[Dict[str, Any]]:
        """
        Get transcript segments.

        Returns:
            List of transcript segments
        """
        return self.segments

    def get_speaker_map(self) -> Dict[str, str]:
        """
        Get speaker map derived from transcript metadata or segments.

        Returns:
            Dictionary mapping grouping_key to display_name (for backward compatibility)
        """
        if self._speaker_map_metadata:
            return self._speaker_map_metadata

        derived_map: Dict[str, str] = {}
        for segment in self.segments:
            speaker = segment.get("speaker")
            if speaker is None:
                continue
            speaker_key = str(speaker)
            if speaker_key not in derived_map:
                derived_map[speaker_key] = speaker_key

        if derived_map:
            return derived_map
        return self.speaker_map

    def get_base_name(self) -> str:
        """
        Get base name for file naming.

        Returns:
            Base name string
        """
        return self.base_name

    def get_transcript_dir(self) -> str:
        """
        Get transcript output directory.

        Returns:
            Transcript directory path
        """
        return self.transcript_dir

    def get_transcript_key(self) -> str:
        return self.transcript_key

    def get_run_id(self) -> Optional[str]:
        return self.run_id

    def get_runtime_flags(self) -> Dict[str, Any]:
        return self.runtime_flags

    def get_speaker_display_name(self, speaker_label: str) -> str:
        if (
            self._speaker_map_metadata
            and speaker_label in self._speaker_map_metadata
        ):
            return f"{self._speaker_map_metadata[speaker_label]} ({speaker_label})"
        return speaker_label

    def set_segments(self, segments: List[Dict[str, Any]]) -> None:
        """
        Set transcript segments (for cases where segments need to be overridden).

        Args:
            segments: List of transcript segments to set

        Raises:
            RuntimeError: If context is frozen
        """
        if self._frozen:
            raise RuntimeError("Cannot modify frozen PipelineContext")
        self.segments = segments
        logger.debug(f"Updated segments in context: {len(segments)} segments")

    def store_analysis_result(self, module_name: str, result: Any) -> None:
        """
        Store analysis result for a module.

        Args:
            module_name: Name of the analysis module
            result: Analysis result to store

        Raises:
            RuntimeError: If context is frozen

        Note:
            Modules should use the output service instead of mutating context
            directly. This method is for backward compatibility.
        """
        if self._frozen:
            raise RuntimeError(
                "Cannot modify frozen PipelineContext - use output service instead"
            )
        self._analysis_results[module_name] = result
        logger.debug(f"Stored analysis result for module: {module_name}")

    def get_analysis_result(self, module_name: str) -> Optional[Any]:
        """
        Get stored analysis result for a module.

        Args:
            module_name: Name of the analysis module

        Returns:
            Stored analysis result or None if not found
        """
        return self._analysis_results.get(module_name)

    def store_computed_value(self, key: str, value: Any) -> None:
        """
        Store a computed value that can be reused.

        Args:
            key: Key for the computed value
            value: Value to store

        Raises:
            RuntimeError: If context is frozen
        """
        if self._frozen:
            raise RuntimeError("Cannot modify frozen PipelineContext")
        self._computed_values[key] = value
        logger.debug(f"Stored computed value: {key}")

    def get_computed_value(self, key: str) -> Optional[Any]:
        """
        Get a stored computed value.

        Args:
            key: Key for the computed value

        Returns:
            Stored value or None if not found
        """
        return self._computed_values.get(key)

    def has_computed_value(self, key: str) -> bool:
        """
        Check if a computed value exists.

        Args:
            key: Key for the computed value

        Returns:
            True if value exists, False otherwise
        """
        return key in self._computed_values

    def get_transcript_service(self) -> TranscriptService:
        """
        Get the TranscriptService instance.

        Returns:
            TranscriptService instance
        """
        return self._transcript_service

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.close()
        return False  # Don't suppress exceptions


class ReadOnlyPipelineContext:
    """
    Read-only wrapper for PipelineContext.

    This wrapper prevents mutations to the context, making it safe
    for parallel execution. All read operations are passed through,
    but write operations raise RuntimeError.
    """

    def __init__(self, context: PipelineContext):
        """
        Initialize read-only wrapper.

        Args:
            context: The PipelineContext to wrap
        """
        self._context = context

    # Delegate all read operations
    def get_segments(self) -> List[Dict[str, Any]]:
        """Get transcript segments."""
        return self._context.get_segments()

    def get_speaker_map(self) -> Dict[str, str]:
        """Get speaker map."""
        return self._context.get_speaker_map()

    def get_base_name(self) -> str:
        """Get base name."""
        return self._context.get_base_name()

    def get_transcript_dir(self) -> str:
        """Get transcript directory."""
        return self._context.get_transcript_dir()

    def get_transcript_key(self) -> str:
        return self._context.get_transcript_key()

    def get_run_id(self) -> Optional[str]:
        return self._context.get_run_id()

    def get_runtime_flags(self) -> Dict[str, Any]:
        return self._context.get_runtime_flags()

    def get_speaker_display_name(self, speaker_label: str) -> str:
        return self._context.get_speaker_display_name(speaker_label)

    def get_analysis_result(self, module_name: str) -> Optional[Any]:
        """Get stored analysis result."""
        return self._context.get_analysis_result(module_name)

    def get_computed_value(self, key: str) -> Optional[Any]:
        """Get stored computed value."""
        return self._context.get_computed_value(key)

    def has_computed_value(self, key: str) -> bool:
        """Check if computed value exists."""
        return self._context.has_computed_value(key)

    def get_transcript_service(self):
        """Get TranscriptService instance."""
        return self._context.get_transcript_service()

    # Block all write operations
    def set_segments(self, segments: List[Dict[str, Any]]) -> None:
        """Blocked: Cannot modify read-only context."""
        raise RuntimeError("Cannot modify read-only PipelineContext")

    def store_analysis_result(self, module_name: str, result: Any) -> None:
        """Blocked: Cannot modify read-only context."""
        raise RuntimeError(
            "Cannot modify read-only PipelineContext - use output service instead"
        )

    def store_computed_value(self, key: str, value: Any) -> None:
        """Blocked: Cannot modify read-only context."""
        raise RuntimeError("Cannot modify read-only PipelineContext")

    # Expose read-only properties
    @property
    def transcript_path(self) -> str:
        """Get transcript path (read-only)."""
        return self._context.transcript_path

    @property
    def segments(self) -> List[Dict[str, Any]]:
        """Get segments (read-only)."""
        return self._context.segments

    @property
    def speaker_map(self) -> Dict[str, str]:
        """Get speaker map (read-only)."""
        return self._context.speaker_map

    @property
    def base_name(self) -> str:
        """Get base name (read-only)."""
        return self._context.base_name

    @property
    def transcript_dir(self) -> str:
        """Get transcript directory (read-only)."""
        return self._context.transcript_dir

    @property
    def transcript_key(self) -> str:
        return self._context.transcript_key

    @property
    def run_id(self) -> Optional[str]:
        return self._context.run_id

    @property
    def runtime_flags(self) -> Dict[str, Any]:
        return self._context.runtime_flags
