"""
Pluggable path resolution system for TranscriptX.

This module provides a flexible, testable path resolution system with pluggable
strategies, decoupled from the state file implementation.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Literal, Any
from enum import Enum

from transcriptx.core.utils._path_cache import (
    _get_cache,
    _get_cache_ttl,
    _manage_cache_size,
)
from transcriptx.core.utils._path_core import get_base_name, get_canonical_base_name
from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils.path_resolution_core import (
    get_path_from_state,
    heuristic_search,
    try_canonical_base_match,
    try_suffix_variants,
    validate_resolved_file_type,
)


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
        if path_obj.exists() and validate_resolved_file_type(path_obj, file_type):
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
        """Resolve path using processing state (full state-path matching)."""
        if self.state_loader is not None:
            try:
                state = self.state_loader(validate=False)
                processed_files = state.get("processed_files", {})

                for _key, entry in processed_files.items():
                    entry_path = entry.get("transcript_path")
                    if entry_path and self._paths_match(entry_path, file_path):
                        resolved_path = entry_path

                        if self.validate_paths and not Path(resolved_path).exists():
                            continue

                        return PathResolutionResult(
                            path=resolved_path,
                            confidence=ResolutionConfidence.HIGH,
                            strategy=self.name,
                            message=f"Found in state file: {resolved_path}",
                        )
            except Exception:
                pass

            return None

        path = get_path_from_state(file_path, file_type, validate=self.validate_paths)
        if path:
            return PathResolutionResult(
                path=str(Path(path).resolve()),
                confidence=ResolutionConfidence.HIGH,
                strategy=self.name,
                message=f"Found in state file: {path}",
            )
        return None

    def _paths_match(self, path1: str, path2: str) -> bool:
        """Check if two paths match (exact or by canonical base name)."""
        if path1 == path2:
            return True

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
        canonical_base = get_canonical_base_name(file_path)

        if file_type in ("transcript", "audio", "output_dir"):
            resolved = try_canonical_base_match(canonical_base, file_type)
            if resolved:
                return PathResolutionResult(
                    path=resolved,
                    confidence=ResolutionConfidence.HIGH,
                    strategy=self.name,
                    message=f"Found by canonical base name: {canonical_base}",
                )
            return None

        search_dir = paths_module.OUTPUTS_DIR
        candidate = Path(search_dir) / f"{canonical_base}.json"
        if candidate.exists():
            return PathResolutionResult(
                path=str(candidate.resolve()),
                confidence=ResolutionConfidence.HIGH,
                strategy=self.name,
                message=f"Found by canonical base name: {canonical_base}",
            )
        matches = sorted(
            Path(search_dir).rglob(f"{canonical_base}.json"),
            key=lambda path: str(path),
        )
        if matches:
            return PathResolutionResult(
                path=str(matches[0].resolve()),
                confidence=ResolutionConfidence.MEDIUM,
                strategy=self.name,
                message=f"Found by canonical base in subdir: {canonical_base}",
            )

        return None


class TranscriptHeuristicCacheStrategy(PathResolutionStrategy):
    """Return a prior heuristic resolution from cache (transcripts only)."""

    use_cache: bool = True

    @property
    def name(self) -> str:
        return "heuristic_cache"

    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        if not self.use_cache or file_type != "transcript":
            return None
        cache_key = (file_path, file_type)
        cache = _get_cache()
        ttl = _get_cache_ttl()
        if cache_key in cache:
            cached_result, cached_time = cache[cache_key]
            if time.time() - cached_time < ttl and Path(cached_result).exists():
                return PathResolutionResult(
                    path=cached_result,
                    confidence=ResolutionConfidence.LOW,
                    strategy=self.name,
                    message="Cached heuristic resolution",
                )
        return None


class SuffixVariantStrategy(PathResolutionStrategy):
    """Try alternate base names when suffix stripping differs."""

    @property
    def name(self) -> str:
        return "suffix_variant"

    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        base_name = get_base_name(file_path)
        canonical_base = get_canonical_base_name(file_path)
        resolved = try_suffix_variants(base_name, canonical_base, file_type)
        if resolved:
            return PathResolutionResult(
                path=resolved,
                confidence=ResolutionConfidence.MEDIUM,
                strategy=self.name,
                message=f"Suffix variant match: {base_name}",
            )
        return None


class HeuristicSearchStrategy(PathResolutionStrategy):
    """Expensive filesystem/state heuristics; may cache transcript results."""

    use_cache: bool = True

    @property
    def name(self) -> str:
        return "heuristic_search"

    def resolve(
        self,
        file_path: str,
        file_type: Literal["transcript", "speaker_map", "audio", "output_dir"],
    ) -> Optional[PathResolutionResult]:
        resolved = heuristic_search(file_path, file_type)
        if resolved:
            if self.use_cache and file_type == "transcript":
                cache_key = (file_path, file_type)
                cache = _get_cache()
                cache[cache_key] = (resolved, time.time())
                _manage_cache_size()
            return PathResolutionResult(
                path=resolved,
                confidence=ResolutionConfidence.LOW,
                strategy=self.name,
                message="Heuristic search",
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
            TranscriptHeuristicCacheStrategy(),
            StateFilePathStrategy(validate_paths=True),
            ExactPathStrategy(),
            CanonicalBaseStrategy(),
            SuffixVariantStrategy(),
            HeuristicSearchStrategy(),
        ]

    def _prepare_resolve(self, validate_state: bool, use_cache: bool) -> None:
        for strategy in self.strategies:
            if isinstance(strategy, StateFilePathStrategy):
                strategy.validate_paths = validate_state
            if isinstance(
                strategy, (TranscriptHeuristicCacheStrategy, HeuristicSearchStrategy)
            ):
                strategy.use_cache = use_cache

    def resolve(
        self,
        file_path: str,
        file_type: Literal[
            "transcript", "speaker_map", "audio", "output_dir"
        ] = "transcript",
        validate_state: bool = True,
        use_cache: bool = True,
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
        self._prepare_resolve(validate_state, use_cache)

        for strategy in self.strategies:
            result = strategy.resolve(file_path, file_type)
            if result and result.found:
                return result.path

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
        use_cache: bool = True,
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
        self._prepare_resolve(validate_state, use_cache)

        for strategy in self.strategies:
            result = strategy.resolve(file_path, file_type)
            if result and result.found:
                return result

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
        use_cache: bool = True,
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
        start_time = time.time()

        self._prepare_resolve(validate_state, use_cache)

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


# Process-wide default resolver (singleton via get_default_resolver)
_default_resolver: Optional[PathResolver] = None


def get_default_resolver() -> PathResolver:
    """Get the default path resolver instance."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = PathResolver()
    return _default_resolver
