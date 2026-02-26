"""
Pluggable path resolution system for TranscriptX.

This module provides a flexible, testable path resolution system with pluggable
strategies, decoupled from the state file implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Literal, Any
from enum import Enum


class ResolutionConfidence(Enum):
    """Confidence level for path resolution results."""

    EXACT = "exact"  # Exact match, highest confidence
    HIGH = "high"  # Strong match (e.g., canonical base name)
    MEDIUM = "medium"  # Moderate match (e.g., suffix variant)
    LOW = "low"  # Weak match (e.g., heuristic search)
    NONE = "none"  # No match found


@dataclass
class PathResolutionResult:
    """
    Result of a path resolution attempt.

    Attributes:
        path: Resolved path if found, None otherwise
        confidence: Confidence level of the resolution
        strategy: Name of the strategy that found the path
        message: Optional message explaining the resolution
    """

    path: Optional[str]
    confidence: ResolutionConfidence
    strategy: str
    message: Optional[str] = None

    @property
    def found(self) -> bool:
        """Whether a path was found."""
        return self.path is not None


class PathResolutionStrategy(ABC):
    """
    Abstract base class for path resolution strategies.

    Each strategy implements a specific method for finding files,
    such as state file lookup, exact match, or heuristic search.
    """

    @abstractmethod
    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        """
        Attempt to resolve a file path using this strategy.

        Args:
            file_path: Original or expected file path
            file_type: Type of file to resolve

        Returns:
            PathResolutionResult if found, None otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this strategy for logging/debugging."""
        pass


class ExactPathStrategy(PathResolutionStrategy):
    """Strategy that checks if the exact path exists."""

    @property
    def name(self) -> str:
        return "exact_path"

    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        path_obj = Path(file_path)
        if path_obj.exists():
            return PathResolutionResult(
                path=str(path_obj.resolve()),
                confidence=ResolutionConfidence.EXACT,
                strategy=self.name,
                message=f"Exact path match: {file_path}",
            )
        return None


class StateFilePathStrategy(PathResolutionStrategy):
    """
    Strategy that looks up paths from the processing state file.

    This strategy is decoupled from the state file implementation,
    making it testable with mock state data.
    """

    def __init__(self, state_loader=None, validate_paths: bool = True):
        """
        Initialize state file strategy.

        Args:
            state_loader: Function that loads processing state (default: load_processing_state)
            validate_paths: Whether to validate that paths exist before returning them
        """
        self.state_loader = state_loader
        self.validate_paths = validate_paths

    @property
    def name(self) -> str:
        return "state_file"

    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        """
        Resolve path using processing state file.

        This is a simplified version that can be extended to match
        the full logic from _get_path_from_state().
        """
        if self.state_loader is None:
            # Lazy import to avoid circular dependencies
            from transcriptx.cli.processing_state import load_processing_state

            self.state_loader = load_processing_state

        try:
            state = self.state_loader(validate=False)
            processed_files = state.get("processed_files", {})

            # Search for entry matching this path
            for key, entry in processed_files.items():
                # Check main transcript_path
                entry_path = entry.get("transcript_path")
                if entry_path and self._paths_match(entry_path, file_path):
                    resolved_path = entry_path

                    # Validate path exists if requested
                    if self.validate_paths and not Path(resolved_path).exists():
                        continue

                    return PathResolutionResult(
                        path=resolved_path,
                        confidence=ResolutionConfidence.HIGH,
                        strategy=self.name,
                        message=f"Found in state file: {resolved_path}",
                    )
        except Exception:
            # If state file access fails, this strategy cannot resolve
            pass

        return None

    def _paths_match(self, path1: str, path2: str) -> bool:
        """Check if two paths match (exact or by canonical base name)."""
        if path1 == path2:
            return True

        # Try canonical base name match
        from transcriptx.core.utils._path_core import get_canonical_base_name

        base1 = get_canonical_base_name(path1)
        base2 = get_canonical_base_name(path2)
        return base1 == base2


class CanonicalBaseStrategy(PathResolutionStrategy):
    """Strategy that searches using canonical base name."""

    @property
    def name(self) -> str:
        return "canonical_base"

    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        from transcriptx.core.utils._path_core import get_canonical_base_name
        from transcriptx.core.utils.paths import (
            DIARISED_TRANSCRIPTS_DIR,
            OUTPUTS_DIR,
            RECORDINGS_DIR,
        )

        canonical_base = get_canonical_base_name(file_path)

        # Try standard locations based on file type
        search_dirs = []
        if file_type == "transcript":
            search_dirs = [DIARISED_TRANSCRIPTS_DIR]
        elif file_type == "speaker_map":
            search_dirs = [OUTPUTS_DIR]
        elif file_type == "audio":
            search_dirs = [RECORDINGS_DIR]
        elif file_type == "output_dir":
            search_dirs = [OUTPUTS_DIR]

        for search_dir in search_dirs:
            # Try with .json extension for transcripts and speaker maps
            if file_type in ["transcript", "speaker_map"]:
                candidate = Path(search_dir) / f"{canonical_base}.json"
                if candidate.exists():
                    return PathResolutionResult(
                        path=str(candidate.resolve()),
                        confidence=ResolutionConfidence.HIGH,
                        strategy=self.name,
                        message=f"Found by canonical base name: {canonical_base}",
                    )
                # Fallback: search subdirectories for canonical base
                matches = sorted(
                    Path(search_dir).rglob(f"{canonical_base}.json"),
                    key=lambda path: str(path),
                )
                if matches:
                    return PathResolutionResult(
                        path=str(matches[0].resolve()),
                        confidence=ResolutionConfidence.MEDIUM,
                        strategy=self.name,
                        message=(
                            f"Found by canonical base in subdir: {canonical_base}"
                        ),
                    )

            # Try directory for output_dir type
            if file_type == "output_dir":
                candidate = Path(search_dir) / canonical_base
                if candidate.exists() and candidate.is_dir():
                    return PathResolutionResult(
                        path=str(candidate.resolve()),
                        confidence=ResolutionConfidence.HIGH,
                        strategy=self.name,
                        message=f"Found output directory: {canonical_base}",
                    )

        return None


class PathResolver:
    """
    Main path resolver that uses pluggable strategies.

    This class orchestrates multiple resolution strategies in order,
    returning the first successful result or raising FileNotFoundError.
    """

    def __init__(self, strategies: Optional[List[PathResolutionStrategy]] = None):
        """
        Initialize path resolver with strategies.

        Args:
            strategies: List of strategies to use (default: standard strategy order)
        """
        if strategies is None:
            strategies = self._default_strategies()
        self.strategies = strategies

    def _default_strategies(self) -> List[PathResolutionStrategy]:
        """Create default strategy list with standard order."""
        return [
            StateFilePathStrategy(validate_paths=True),
            ExactPathStrategy(),
            CanonicalBaseStrategy(),
            # Note: Suffix variant and heuristic strategies can be added here
        ]

    def resolve(
        self,
        file_path: str,
        file_type: Literal[
            "transcript", "speaker_map", "audio", "output_dir"
        ] = "transcript",
        validate_state: bool = True,
    ) -> str:
        """
        Resolve a file path using all configured strategies.

        Args:
            file_path: Original or expected file path
            file_type: Type of file to resolve
            validate_state: Whether state file strategy should validate paths

        Returns:
            Resolved path to existing file

        Raises:
            FileNotFoundError: If no strategy can resolve the path
        """
        # Update state file strategy validation if needed
        for strategy in self.strategies:
            if isinstance(strategy, StateFilePathStrategy):
                strategy.validate_paths = validate_state
                break

        # Try each strategy in order
        for strategy in self.strategies:
            result = strategy.resolve(file_path, file_type)
            if result and result.found:
                return result.path

        # All strategies failed
        raise FileNotFoundError(
            f"{file_type.replace('_', ' ').title()} not found: {file_path}. "
            f"Tried {len(self.strategies)} strategies."
        )

    def resolve_with_result(
        self,
        file_path: str,
        file_type: Literal[
            "transcript", "speaker_map", "audio", "output_dir"
        ] = "transcript",
        validate_state: bool = True,
    ) -> PathResolutionResult:
        """
        Resolve a file path and return detailed result information.

        This is useful for debugging and understanding which strategy succeeded.

        Args:
            file_path: Original or expected file path
            file_type: Type of file to resolve
            validate_state: Whether state file strategy should validate paths

        Returns:
            PathResolutionResult with resolution details

        Raises:
            FileNotFoundError: If no strategy can resolve the path
        """
        # Update state file strategy validation if needed
        for strategy in self.strategies:
            if isinstance(strategy, StateFilePathStrategy):
                strategy.validate_paths = validate_state
                break

        # Try each strategy in order
        for strategy in self.strategies:
            result = strategy.resolve(file_path, file_type)
            if result and result.found:
                return result

        # All strategies failed
        return PathResolutionResult(
            path=None,
            confidence=ResolutionConfidence.NONE,
            strategy="none",
            message=f"No strategy could resolve: {file_path}",
        )

    def resolve_with_trace(
        self,
        file_path: str,
        file_type: Literal[
            "transcript", "speaker_map", "audio", "output_dir"
        ] = "transcript",
        validate_state: bool = True,
    ) -> Dict[str, Any]:
        """
        Resolve a file path and return detailed trace information.

        This method is useful for debugging and understanding which strategy
        succeeded, what candidates were found, and the resolution process.

        Args:
            file_path: Original or expected file path
            file_type: Type of file to resolve
            validate_state: Whether state file strategy should validate paths

        Returns:
            Dict with:
            - file_path: Original file path
            - file_type: File type
            - strategies_tried: List of strategy names tried
            - candidates_found: Dict mapping strategy name to list of candidates
            - final_result: PathResolutionResult or None
            - execution_time_ms: Time taken in milliseconds
        """
        import time

        start_time = time.time()

        # Update state file strategy validation if needed
        for strategy in self.strategies:
            if isinstance(strategy, StateFilePathStrategy):
                strategy.validate_paths = validate_state
                break

        strategies_tried = []
        candidates_found = {}
        final_result = None

        # Try each strategy and capture results
        for strategy in self.strategies:
            strategy_name = strategy.name
            strategies_tried.append(strategy_name)

            try:
                result = strategy.resolve(file_path, file_type)
                if result and result.found:
                    candidates_found[strategy_name] = [result.path]
                    if final_result is None:
                        final_result = result
                else:
                    candidates_found[strategy_name] = []
            except Exception:
                candidates_found[strategy_name] = []

        execution_time_ms = (time.time() - start_time) * 1000

        return {
            "file_path": file_path,
            "file_type": file_type,
            "strategies_tried": strategies_tried,
            "candidates_found": candidates_found,
            "final_result": (
                {
                    "path": final_result.path if final_result else None,
                    "confidence": (
                        final_result.confidence.value if final_result else None
                    ),
                    "strategy": final_result.strategy if final_result else None,
                    "message": final_result.message if final_result else None,
                }
                if final_result
                else None
            ),
            "execution_time_ms": execution_time_ms,
        }


# Global resolver instance (for backward compatibility)
_default_resolver: Optional[PathResolver] = None


def get_default_resolver() -> PathResolver:
    """Get the default path resolver instance."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = PathResolver()
    return _default_resolver
