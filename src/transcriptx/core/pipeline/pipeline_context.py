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

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.speaker_map_resolver import normalize_diarized_id
from transcriptx.io.transcript_service import TranscriptService
from transcriptx.utils.text_utils import is_eligible_named_speaker

logger = get_logger()


@dataclass(frozen=True)
class LoadedTranscript:
    segments: List[Dict[str, Any]]
    base_name: str
    transcript_dir: str
    transcript_service: TranscriptService


@dataclass(frozen=True)
class SpeakerResolution:
    segments: List[Dict[str, Any]]
    speaker_map: Dict[str, str]
    speaker_map_metadata: Dict[str, str]
    ignored_speaker_ids: set[str]


@dataclass(frozen=True)
class RuntimeIdentityAndFlags:
    transcript_key: str
    run_id: Optional[str]
    runtime_flags: Dict[str, Any]


class PipelineContextBuilder:
    def __init__(
        self,
        *,
        transcript_path: str,
        include_unidentified_speakers: bool = False,
        anonymise_speakers: bool = False,
        batch_mode: bool = False,
        output_dir: Optional[str] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self.transcript_path = transcript_path
        self.include_unidentified_speakers = include_unidentified_speakers
        self.anonymise_speakers = anonymise_speakers
        self.batch_mode = batch_mode
        self.output_dir = output_dir
        self.transcript_key = transcript_key
        self.run_id = run_id

    def load_transcript(self) -> LoadedTranscript:
        transcript_service = TranscriptService(enable_cache=True)
        try:
            segments, base_name, transcript_dir = (
                transcript_service.load_transcript_data(
                    self.transcript_path,
                    batch_mode=self.batch_mode,
                    use_cache=True,
                    output_dir=self.output_dir,
                )
            )
        except FileNotFoundError:
            logger.error(f"Transcript file not found: {self.transcript_path}")
            raise
        except ValueError as e:
            logger.error(f"Invalid transcript data: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load transcript data: {e}")
            raise RuntimeError(f"Failed to initialize PipelineContext: {e}") from e
        return LoadedTranscript(
            segments=segments,
            base_name=base_name,
            transcript_dir=transcript_dir,
            transcript_service=transcript_service,
        )

    def resolve_speakers(self, loaded: LoadedTranscript) -> SpeakerResolution:
        # Contract: speaker display state is a module-global bridge used by
        # legacy output helpers. A builder invocation may set it once from the
        # resolved metadata, and PipelineContext.close() clears it.
        from transcriptx.core.utils.speaker_extraction import (
            get_unique_speakers,
            set_speaker_display_map,
        )
        from transcriptx.io.speaker_map_resolver import SpeakerMapResolver

        resolver = SpeakerMapResolver()
        state = resolver.load_mapping(self.transcript_path)
        ignored_speaker_ids = set(state.ignored_speakers)
        segments = loaded.segments
        if state.speaker_map:
            segments = resolver.resolve_segments(segments, state)
            loaded.transcript_service.replace_cached_segments(
                self.transcript_path, segments
            )

        speaker_map = get_unique_speakers(segments)
        logger.debug(f"Extracted {len(speaker_map)} speakers from segments")
        speaker_map_metadata = (
            state.speaker_map or self._derive_speaker_map_from_segments(segments)
        )
        if speaker_map_metadata:
            set_speaker_display_map(speaker_map_metadata)
        return SpeakerResolution(
            segments=segments,
            speaker_map=speaker_map,
            speaker_map_metadata=speaker_map_metadata,
            ignored_speaker_ids=ignored_speaker_ids,
        )

    def compute_identity_and_runtime_flags(
        self, speaker_resolution: SpeakerResolution
    ) -> RuntimeIdentityAndFlags:
        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )

        transcript_key = self.transcript_key or compute_transcript_identity_hash(
            speaker_resolution.segments
        )
        runtime_flags: Dict[str, Any] = {
            "include_unidentified_speakers": self.include_unidentified_speakers,
            "anonymise_speakers": self.anonymise_speakers,
            "ignored_speaker_ids": speaker_resolution.ignored_speaker_ids,
        }
        if self.anonymise_speakers:
            runtime_flags["speaker_anonymisation_map"] = (
                self._build_speaker_anonymisation_map(speaker_resolution.segments)
            )
        runtime_flags["named_speaker_keys"] = self._collect_named_speaker_keys(
            speaker_resolution.segments,
            speaker_resolution.ignored_speaker_ids,
        )
        runtime_flags["speaker_key_aliases"] = self._build_speaker_key_aliases(
            speaker_resolution.speaker_map
        )
        return RuntimeIdentityAndFlags(
            transcript_key=transcript_key,
            run_id=self.run_id,
            runtime_flags=runtime_flags,
        )

    @staticmethod
    def _get_speaker_key_from_segment(segment: Dict[str, Any]) -> Optional[str]:
        key = segment.get("speaker_db_id")
        if key:
            return str(key).strip() or None
        key = segment.get("speaker_key") or segment.get("grouping_key")
        if key:
            return str(key).strip() or None
        key = segment.get("speaker")
        if key:
            return str(key).strip() or None
        return None

    @classmethod
    def _collect_named_speaker_keys(
        cls, segments: List[Dict[str, Any]], ignored_speaker_ids: set[str]
    ) -> set[str]:
        named_keys: set[str] = set()
        for segment in segments:
            label = segment.get("speaker")
            key = cls._get_speaker_key_from_segment(segment)
            if key and label:
                if is_eligible_named_speaker(str(label), str(key), ignored_speaker_ids):
                    named_keys.add(key)
        return named_keys

    @classmethod
    def _build_speaker_anonymisation_map(
        cls, segments: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        seen: set[str] = set()
        ordered_keys: list[str] = []
        for segment in segments:
            key = cls._get_speaker_key_from_segment(segment)
            if not key or key in seen:
                continue
            seen.add(key)
            ordered_keys.append(key)
        return {
            key: f"Speaker {index:02d}"
            for index, key in enumerate(ordered_keys, start=1)
        }

    @staticmethod
    def _build_speaker_key_aliases(speaker_map: Dict[Any, Any]) -> Dict[str, str]:
        aliases: Dict[str, str] = {}
        collisions: set[str] = set()
        for key, display in speaker_map.items():
            if display is None:
                continue
            display_str = str(display).strip()
            key_str = str(key).strip()
            if not display_str or not key_str:
                continue
            if display_str in aliases and aliases[display_str] != key_str:
                collisions.add(display_str)
                continue
            aliases[display_str] = key_str
        for display in collisions:
            aliases.pop(display, None)
        return aliases

    @staticmethod
    def _derive_speaker_map_from_segments(
        segments: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        from collections import Counter

        votes: Dict[str, Counter[str]] = {}
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            speaker_id = seg.get("speaker")
            if not isinstance(speaker_id, str) or not speaker_id.strip():
                continue
            original_cue = seg.get("original_cue")
            if not isinstance(original_cue, dict):
                continue
            original_name = original_cue.get("original_speaker")
            if not isinstance(original_name, str) or not original_name.strip():
                continue
            sid = speaker_id.strip()
            name = original_name.strip()
            bucket = votes.setdefault(sid, Counter())
            bucket[name] += 1

        resolved: Dict[str, str] = {}
        for sid, counter in votes.items():
            if not counter:
                continue
            resolved[sid] = sorted(
                counter.items(), key=lambda item: (-item[1], item[0])
            )[0][0]

        if resolved:
            logger.info(
                f"Recovered {len(resolved)} speaker name(s) from original_cue metadata"
            )
        return resolved


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
        include_unidentified_speakers: bool = False,
        anonymise_speakers: bool = False,
        batch_mode: bool = False,
        output_dir: Optional[str] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        """
        Initialize the pipeline context.

        Args:
            transcript_path: Path to the transcript file
            include_unidentified_speakers: Include unidentified speakers in per-speaker outputs
            anonymise_speakers: Anonymise speaker display names in outputs
            batch_mode: Whether running in batch mode

        Raises:
            FileNotFoundError: If transcript file doesn't exist
            ValueError: If transcript data is invalid
            RuntimeError: If context initialization fails
        """
        self.transcript_path = transcript_path
        builder = PipelineContextBuilder(
            transcript_path=transcript_path,
            include_unidentified_speakers=include_unidentified_speakers,
            anonymise_speakers=anonymise_speakers,
            batch_mode=batch_mode,
            output_dir=output_dir,
            transcript_key=transcript_key,
            run_id=run_id,
        )
        loaded = builder.load_transcript()
        speaker_resolution = builder.resolve_speakers(loaded)
        runtime = builder.compute_identity_and_runtime_flags(speaker_resolution)

        self._transcript_service = loaded.transcript_service
        self.segments = speaker_resolution.segments
        self.base_name = loaded.base_name
        self.transcript_dir = loaded.transcript_dir
        self.ignored_speaker_ids = speaker_resolution.ignored_speaker_ids
        self.speaker_map = speaker_resolution.speaker_map
        self.transcript_key = runtime.transcript_key
        self.run_id = runtime.run_id
        self._speaker_map_metadata = speaker_resolution.speaker_map_metadata

        # Cache for analysis results (keyed by module name)
        self._analysis_results: Dict[str, Any] = {}
        self.runtime_flags = runtime.runtime_flags

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

    def _collect_named_speaker_keys(self, segments: List[Dict[str, Any]]) -> set[str]:
        named_keys: set[str] = set()
        for segment in segments:
            label = segment.get("speaker")
            key = self.get_speaker_key_from_segment(segment)
            if key and label:
                if is_eligible_named_speaker(
                    str(label), str(key), self.ignored_speaker_ids
                ):
                    named_keys.add(key)
        return named_keys

    def _derive_speaker_map_from_segments(
        self, segments: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Build SPEAKER_XX -> original speaker map from embedded import metadata.

        This recovers imported names when the sidecar is missing/stale but
        segments still carry original_cue.original_speaker from import.
        """
        from collections import Counter

        votes: Dict[str, Counter[str]] = {}
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            speaker_id = seg.get("speaker")
            if not isinstance(speaker_id, str) or not speaker_id.strip():
                continue
            original_cue = seg.get("original_cue")
            if not isinstance(original_cue, dict):
                continue
            original_name = original_cue.get("original_speaker")
            if not isinstance(original_name, str) or not original_name.strip():
                continue
            sid = speaker_id.strip()
            name = original_name.strip()
            bucket = votes.setdefault(sid, Counter())
            bucket[name] += 1

        resolved: Dict[str, str] = {}
        for sid, counter in votes.items():
            if not counter:
                continue
            resolved[sid] = sorted(
                counter.items(), key=lambda item: (-item[1], item[0])
            )[0][0]

        if resolved:
            logger.info(
                f"Recovered {len(resolved)} speaker name(s) from original_cue metadata"
            )
        return resolved

    def _build_speaker_key_aliases(self, speaker_map: Dict[Any, Any]) -> Dict[str, str]:
        aliases: Dict[str, str] = {}
        collisions: set[str] = set()
        for key, display in speaker_map.items():
            if display is None:
                continue
            display_str = str(display).strip()
            key_str = str(key).strip()
            if not display_str or not key_str:
                continue
            if display_str in aliases and aliases[display_str] != key_str:
                collisions.add(display_str)
                continue
            aliases[display_str] = key_str
        for display in collisions:
            aliases.pop(display, None)
        return aliases

    def get_speaker_key_from_segment(self, segment: Dict[str, Any]) -> Optional[str]:
        key = segment.get("speaker_db_id")
        if key:
            return str(key).strip() or None
        key = segment.get("speaker_key") or segment.get("grouping_key")
        if key:
            return str(key).strip() or None
        key = segment.get("speaker")
        if key:
            return str(key).strip() or None
        return None

    def get_speaker_key(self, speaker_like: Any) -> Optional[str]:
        if speaker_like is None:
            return None
        if isinstance(speaker_like, dict):
            return self.get_speaker_key_from_segment(speaker_like)
        key = str(speaker_like).strip()
        return key or None

    def iter_speaker_keys_in_order(self, segments: List[Dict[str, Any]]) -> List[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for segment in segments:
            key = self.get_speaker_key_from_segment(segment)
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return ordered

    def build_speaker_anonymisation_map(
        self, segments: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        ordered_keys = self.iter_speaker_keys_in_order(segments)
        mapping: Dict[str, str] = {}
        for index, key in enumerate(ordered_keys, start=1):
            mapping[key] = f"Speaker {index:02d}"
        return mapping

    def get_speaker_display_name(self, speaker_key: Optional[str]) -> Optional[str]:
        if speaker_key is None:
            return None
        if self.runtime_flags.get("anonymise_speakers"):
            mapping = self.runtime_flags.get("speaker_anonymisation_map", {})
            return mapping.get(speaker_key, speaker_key)
        if self._speaker_map_metadata:
            normalized = normalize_diarized_id(speaker_key)
            map_key = (
                normalized
                if normalized and normalized in self._speaker_map_metadata
                else speaker_key
            )
            if map_key in self._speaker_map_metadata:
                return f"{self._speaker_map_metadata[map_key]} ({speaker_key})"
        return speaker_key

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

    def get_speaker_key_from_segment(self, segment: Dict[str, Any]) -> Optional[str]:
        return self._context.get_speaker_key_from_segment(segment)

    def get_speaker_key(self, speaker_like: Any) -> Optional[str]:
        return self._context.get_speaker_key(speaker_like)

    def iter_speaker_keys_in_order(self, segments: List[Dict[str, Any]]) -> List[str]:
        return self._context.iter_speaker_keys_in_order(segments)

    def get_speaker_display_name(self, speaker_key: Optional[str]) -> Optional[str]:
        return self._context.get_speaker_display_name(speaker_key)

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
