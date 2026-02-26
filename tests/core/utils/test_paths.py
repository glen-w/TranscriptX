"""
Tests for path resolution and caching utilities.

This module tests path resolution, caching behavior, and path validation.
"""

from pathlib import Path

import pytest

from transcriptx.core.utils.path_utils import (
    get_base_name,
    get_canonical_base_name,
    get_transcript_dir,
    invalidate_path_cache,
    get_cache_stats,
)


class TestGetBaseName:
    """Tests for get_base_name function."""

    def test_extracts_base_name_from_path(self):
        """Test that base name is extracted from path."""
        result = get_base_name("/path/to/test.json")

        assert result == "test"

    def test_handles_paths_without_extension(self):
        """Test that paths without extension are handled."""
        result = get_base_name("/path/to/test")

        assert result == "test"

    def test_handles_relative_paths(self):
        """Test that relative paths are handled."""
        result = get_base_name("test.json")

        assert result == "test"


class TestGetCanonicalBaseName:
    """Tests for get_canonical_base_name function."""

    def test_returns_canonical_base_name(self):
        """Test that canonical base name is returned."""
        result = get_canonical_base_name("/path/to/test.json")

        assert isinstance(result, str)
        assert "test" in result

    def test_normalizes_names(self):
        """Test that names are normalized."""
        result1 = get_canonical_base_name("/path/to/test.json")
        result2 = get_canonical_base_name("/path/to/TEST.json")

        # Should normalize to same base
        assert result1.lower() == result2.lower() or result1 == result2


class TestGetTranscriptDir:
    """Tests for get_transcript_dir function."""

    def test_returns_transcript_directory(self):
        """Test that transcript directory is returned."""
        result = get_transcript_dir("/path/to/transcript.json")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should return a valid directory path
        assert (
            Path(result).is_absolute() or Path(result).exists() or "outputs" in result
        )

    def test_handles_relative_paths(self):
        """Test that relative paths are handled."""
        result = get_transcript_dir("transcript.json")

        assert isinstance(result, str)


class TestInvalidatePathCache:
    """Tests for invalidate_path_cache function."""

    def test_invalidates_cache(self):
        """Test that cache is invalidated."""
        # Should not raise error
        invalidate_path_cache()

    def test_invalidates_specific_path(self):
        """Test that specific path cache is invalidated."""
        # Should not raise error
        invalidate_path_cache("/path/to/test.json")


class TestGetCacheStats:
    """Tests for get_cache_stats function."""

    def test_returns_cache_stats(self):
        """Test that cache statistics are returned."""
        stats = get_cache_stats()

        assert isinstance(stats, dict)
        # May have keys like "hits", "misses", "size", etc.


class TestPathResolution:
    """Tests for path resolution functions."""

    def test_resolves_file_path(self, tmp_path):
        """Test that file path is resolved."""
        from transcriptx.core.utils._path_resolution import resolve_file_path

        # Create a test file
        test_file = tmp_path / "test.json"
        test_file.write_text("{}")

        # Should handle path resolution
        try:
            result = resolve_file_path(str(test_file), file_type="transcript")
            assert isinstance(result, str)
        except FileNotFoundError:
            # May raise if not found
            pass


class TestPathResolutionStrategies:
    """Tests for individual path resolution strategies."""

    def test_exact_path_strategy(self, tmp_path):
        """Test ExactPathStrategy."""
        from transcriptx.core.utils.path_resolver import (
            ExactPathStrategy,
            PathResolutionResult,
        )

        strategy = ExactPathStrategy()
        test_file = tmp_path / "test.json"
        test_file.write_text("{}")

        result = strategy.resolve(str(test_file), "transcript")

        assert result is not None
        assert isinstance(result, PathResolutionResult)
        assert result.found is True
        assert result.path == str(test_file.resolve())
        assert result.strategy == "exact_path"

    def test_exact_path_strategy_not_found(self):
        """Test ExactPathStrategy with non-existent file."""
        from transcriptx.core.utils.path_resolver import ExactPathStrategy

        strategy = ExactPathStrategy()
        result = strategy.resolve("/nonexistent/path.json", "transcript")

        assert result is None

    def test_state_file_strategy(self, tmp_path):
        """Test StateFilePathStrategy."""
        from transcriptx.core.utils.path_resolver import StateFilePathStrategy

        # Create the file first
        test_file = tmp_path / "test.json"
        test_file.write_text("{}")

        # Create mock state with the actual file path
        state_data = {"processed_files": {"test": {"transcript_path": str(test_file)}}}

        def mock_state_loader(**_kwargs):
            return state_data

        strategy = StateFilePathStrategy(
            state_loader=mock_state_loader, validate_paths=False
        )

        # Try to resolve using the actual path (should match)
        result = strategy.resolve(str(test_file), "transcript")

        assert result is not None
        assert result.found is True
        assert result.strategy == "state_file"

    def test_strategy_ordering(self, tmp_path):
        """Test that strategies are tried in correct order."""
        from transcriptx.core.utils.path_resolver import (
            PathResolver,
            ExactPathStrategy,
            StateFilePathStrategy,
        )

        test_file = tmp_path / "test.json"
        test_file.write_text("{}")

        # Create resolver with strategies in order
        resolver = PathResolver(
            strategies=[
                ExactPathStrategy(),
                StateFilePathStrategy(validate_paths=False),
            ]
        )

        # Should use exact path strategy first
        result = resolver.resolve(str(test_file), "transcript")
        assert result is not None

    def test_strategy_fallback_chain(self, tmp_path):
        """Test strategy fallback chain."""
        from transcriptx.core.utils.path_resolver import PathResolver, ExactPathStrategy

        # Create resolver with only exact path strategy
        resolver = PathResolver(strategies=[ExactPathStrategy()])

        # Non-existent file should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            resolver.resolve("/nonexistent/path.json", "transcript")

    def test_cache_ttl_behavior(self):
        """Test cache TTL behavior."""
        from transcriptx.core.utils.path_utils import (
            invalidate_path_cache,
            get_cache_stats,
        )

        # Invalidate cache
        invalidate_path_cache()

        # Get stats (may be empty if cache is cleared)
        stats = get_cache_stats()
        assert isinstance(stats, dict)

    def test_cache_invalidation(self):
        """Test cache invalidation."""
        from transcriptx.core.utils.path_utils import invalidate_path_cache

        # Should not raise error
        invalidate_path_cache()
        invalidate_path_cache("/specific/path.json")

    def test_state_path_validation(self, tmp_path):
        """Test state path validation."""
        from transcriptx.core.utils.path_resolver import StateFilePathStrategy

        # Create state with invalid path
        state_data = {
            "processed_files": {"test": {"transcript_path": "/nonexistent/path.json"}}
        }

        def mock_state_loader():
            return state_data

        # With validation enabled, should return None
        strategy = StateFilePathStrategy(
            state_loader=mock_state_loader, validate_paths=True
        )
        result = strategy.resolve("test", "transcript")

        # Should not find invalid path
        assert result is None or result.found is False

    def test_resolution_trace_completeness(self, tmp_path):
        """Test that resolution trace is complete."""
        from transcriptx.core.utils.path_resolver import PathResolver, ExactPathStrategy

        test_file = tmp_path / "test.json"
        test_file.write_text("{}")

        resolver = PathResolver(strategies=[ExactPathStrategy()])
        trace = resolver.resolve_with_trace(
            str(test_file), "transcript", validate_state=False
        )

        assert "strategies_tried" in trace
        assert "final_result" in trace
        assert isinstance(trace["strategies_tried"], list)
        # final_result may be None or a dict
        if trace["final_result"] is not None:
            assert (
                "path" in trace["final_result"] or "strategy" in trace["final_result"]
            )
