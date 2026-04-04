"""
Unit tests for path resolution (ResolutionConfidence, PathResolutionResult, ExactPathStrategy).
"""

from __future__ import annotations

from pathlib import Path


from transcriptx.core.utils.path_resolver import (
    ExactPathStrategy,
    PathResolutionResult,
    ResolutionConfidence,
)


class TestResolutionConfidence:
    """Tests for ResolutionConfidence enum."""

    def test_values(self) -> None:
        """ResolutionConfidence has expected values."""
        assert ResolutionConfidence.EXACT.value == "exact"
        assert ResolutionConfidence.HIGH.value == "high"
        assert ResolutionConfidence.MEDIUM.value == "medium"
        assert ResolutionConfidence.LOW.value == "low"
        assert ResolutionConfidence.NONE.value == "none"


class TestPathResolutionResult:
    """Tests for PathResolutionResult dataclass."""

    def test_found_true_when_path_set(self) -> None:
        """found is True when path is set."""
        r = PathResolutionResult(
            path="/some/path",
            confidence=ResolutionConfidence.EXACT,
            strategy="test",
        )
        assert r.found is True

    def test_found_false_when_path_none(self) -> None:
        """found is False when path is None."""
        r = PathResolutionResult(
            path=None,
            confidence=ResolutionConfidence.NONE,
            strategy="test",
        )
        assert r.found is False

    def test_message_optional(self) -> None:
        """message is optional."""
        r = PathResolutionResult(
            path="/p",
            confidence=ResolutionConfidence.EXACT,
            strategy="test",
            message="found it",
        )
        assert r.message == "found it"


class TestExactPathStrategy:
    """Tests for ExactPathStrategy."""

    def test_name(self) -> None:
        """ExactPathStrategy has correct name."""
        strategy = ExactPathStrategy()
        assert strategy.name == "exact_path"

    def test_resolve_existing_file(self, tmp_path: Path) -> None:
        """resolve returns result for existing file."""
        f = tmp_path / "transcript.json"
        f.write_text("{}")

        strategy = ExactPathStrategy()
        result = strategy.resolve(str(f), "transcript")

        assert result is not None
        assert result.found is True
        assert result.confidence == ResolutionConfidence.EXACT
        assert result.strategy == "exact_path"

    def test_resolve_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """resolve returns None for nonexistent file."""
        strategy = ExactPathStrategy()
        result = strategy.resolve(str(tmp_path / "missing.json"), "transcript")

        assert result is None
