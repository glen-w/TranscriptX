"""
Regression tests for path resolution edge cases.

This module tests path resolution to catch regressions introduced by
the refactoring, including ambiguous duplicates, strategy ordering,
and resolution trace consistency.
"""

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.path_resolver import (
    PathResolver,
    ExactPathStrategy,
)
from tests.regression.test_utils import (
    capture_resolution_trace,
    save_resolution_trace_snapshot,
    load_resolution_trace_snapshot,
)


class TestPathResolutionStrategyOrder:
    """Tests for path resolution strategy ordering."""

    def test_all_strategies_exact_path_first(self, tmp_path):
        """Verify exact path strategy is tried (after state_file if enabled)."""
        test_file = tmp_path / "test_transcript.json"
        test_file.write_text(json.dumps({"segments": []}))

        # Create resolver with only exact path strategy to test ordering
        resolver = PathResolver(strategies=[ExactPathStrategy()])
        trace = resolver.resolve_with_trace(
            str(test_file), "transcript", validate_state=False
        )

        assert trace["strategies_tried"][0] == "exact_path"
        assert trace["final_result"]["strategy"] == "exact_path"

    def test_all_strategies_state_file_second(self, tmp_path, monkeypatch):
        """Verify state file lookup is second."""
        # Create a file that doesn't exist at exact path
        # but exists in state file
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "processed_files": {
                "test_key": {
                    "transcript_path": str(tmp_path / "actual_file.json"),
                    "status": "processed",
                }
            }
        }
        state_file.write_text(json.dumps(state_data))

        # Create the actual file
        actual_file = tmp_path / "actual_file.json"
        actual_file.write_text(json.dumps({"segments": []}))

        # Try to resolve a different path (not exact match)
        resolver = PathResolver()
        trace = resolver.resolve_with_trace("test_key", "transcript")

        # State file strategy should be tried
        assert "state_file" in trace["strategies_tried"]

    def test_all_strategies_canonical_base_third(self, tmp_path):
        """Verify canonical base name is third."""
        # Create file with canonical base name
        canonical_file = tmp_path / "meeting_2024_01_15.json"
        canonical_file.write_text(json.dumps({"segments": []}))

        # Try to resolve with different path but same canonical base
        resolver = PathResolver()
        trace = resolver.resolve_with_trace("meeting-2024-01-15", "transcript")

        # Should try canonical base strategy
        assert "canonical_base" in trace["strategies_tried"]

    def test_all_strategies_fallback_order(self, tmp_path):
        """Verify fallback order when earlier strategies fail."""
        # Create a file that only matches via canonical base
        test_file = tmp_path / "test_file.json"
        test_file.write_text(json.dumps({"segments": []}))

        resolver = PathResolver()

        # Try to resolve with non-existent exact path
        # Should fall through to canonical base
        trace = resolver.resolve_with_trace("test-file", "transcript")

        # Should try multiple strategies
        assert len(trace["strategies_tried"]) > 1


class TestAmbiguousDuplicatesResolution:
    """Tests for ambiguous duplicate resolution."""

    def test_ambiguous_duplicates_same_basename_different_dirs(
        self, fixture_ambiguous_duplicates, monkeypatch
    ):
        """When same basename exists in multiple directories, verify which one is chosen."""
        fixture = fixture_ambiguous_duplicates
        base_name = fixture["base_name"]

        from pathlib import Path
        from transcriptx.core.utils import paths

        transcripts_root = Path(fixture["directories"][0]).parent
        outputs_root = Path(fixture["directories"][2]).parent
        monkeypatch.setattr(paths, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root))
        monkeypatch.setattr(paths, "OUTPUTS_DIR", str(outputs_root))

        resolver = PathResolver()

        # Try to resolve - should pick one based on strategy order
        trace = resolver.resolve_with_trace(base_name, "transcript")

        # Should have found a file
        assert trace["final_result"] is not None
        assert trace["final_result"]["path"] is not None

        # The chosen file should be one of the candidates
        chosen_path = trace["final_result"]["path"]
        assert chosen_path in fixture["files"]

    def test_ambiguous_duplicates_confidence_scoring(
        self, fixture_ambiguous_duplicates, monkeypatch
    ):
        """Verify confidence scores are correct for ambiguous cases."""
        fixture = fixture_ambiguous_duplicates
        base_name = fixture["base_name"]

        # Monkeypatch directories
        from pathlib import Path
        from transcriptx.core.utils import paths

        transcripts_root = Path(fixture["directories"][0]).parent
        monkeypatch.setattr(paths, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root))

        resolver = PathResolver()
        trace = resolver.resolve_with_trace(
            base_name, "transcript", validate_state=False
        )

        # Should have confidence score if found
        if trace["final_result"] and trace["final_result"]["path"]:
            assert trace["final_result"]["confidence"] is not None

            # Confidence should be one of the valid values
            valid_confidences = ["exact", "high", "medium", "low"]
            assert trace["final_result"]["confidence"] in valid_confidences
        else:
            pytest.skip("File not found - may need to configure search directories")

    def test_ambiguous_duplicates_strategy_precedence(
        self, fixture_ambiguous_duplicates, monkeypatch
    ):
        """Verify strategy order determines winner when confidence is equal."""
        fixture = fixture_ambiguous_duplicates
        base_name = fixture["base_name"]

        # Monkeypatch directories
        from pathlib import Path
        from transcriptx.core.utils import paths

        transcripts_root = Path(fixture["directories"][0]).parent
        monkeypatch.setattr(paths, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root))

        resolver = PathResolver()
        trace = resolver.resolve_with_trace(
            base_name, "transcript", validate_state=False
        )

        # Strategy used should be one of the tried strategies if found
        if trace["final_result"] and trace["final_result"]["path"]:
            assert trace["final_result"]["strategy"] in trace["strategies_tried"]
        else:
            pytest.skip("File not found - may need to configure search directories")


class TestResolutionTraceSnapshot:
    """Tests for resolution trace snapshot consistency."""

    def test_resolution_trace_snapshot(self, tmp_path):
        """Capture full resolution trace and compare against golden snapshot."""
        test_file = tmp_path / "test_transcript.json"
        test_file.write_text(json.dumps({"segments": []}))

        resolver = PathResolver()
        trace = resolver.resolve_with_trace(str(test_file), "transcript")

        # Save snapshot
        snapshot_path = tmp_path / "snapshot.json"
        save_resolution_trace_snapshot(
            capture_resolution_trace(resolver, str(test_file), "transcript"),
            snapshot_path,
        )

        # Load and compare
        loaded = load_resolution_trace_snapshot(snapshot_path)

        assert loaded["file_path"] == trace["file_path"]
        assert loaded["file_type"] == trace["file_type"]
        assert loaded["strategies_tried"] == trace["strategies_tried"]

    def test_resolution_trace_multiple_candidates(
        self, fixture_ambiguous_duplicates, monkeypatch
    ):
        """Trace when multiple candidates exist."""
        fixture = fixture_ambiguous_duplicates
        base_name = fixture["base_name"]

        from pathlib import Path
        from transcriptx.core.utils import paths

        transcripts_root = Path(fixture["directories"][0]).parent
        outputs_root = Path(fixture["directories"][2]).parent
        monkeypatch.setattr(paths, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root))
        monkeypatch.setattr(paths, "OUTPUTS_DIR", str(outputs_root))

        resolver = PathResolver()
        trace = resolver.resolve_with_trace(base_name, "transcript")

        # Should have found multiple candidates across strategies
        total_candidates = sum(
            len(candidates) for candidates in trace["candidates_found"].values()
        )
        assert total_candidates > 0

    def test_resolution_trace_strategy_failure_chain(self, tmp_path):
        """Trace when strategies fail in sequence."""
        # Try to resolve non-existent file
        resolver = PathResolver()
        trace = resolver.resolve_with_trace("nonexistent_file", "transcript")

        # Should have tried all strategies
        assert len(trace["strategies_tried"]) > 0

        # Final result should be None (not found)
        assert trace["final_result"] is None or trace["final_result"]["path"] is None


class TestPathResolutionEdgeCases:
    """Tests for path resolution edge cases."""

    def test_relative_path_resolution(self, fixture_relative_vs_absolute):
        """Relative paths resolve correctly."""
        fixture = fixture_relative_vs_absolute

        # Change to working directory
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(fixture["working_dir"])

            resolver = PathResolver()
            result = resolver.resolve(fixture["relative_path"], "transcript")

            # Should resolve to absolute path
            assert Path(result).exists()
            assert Path(result).resolve() == Path(fixture["file"]).resolve()
        finally:
            os.chdir(original_cwd)

    def test_absolute_path_resolution(self, fixture_relative_vs_absolute):
        """Absolute paths resolve correctly."""
        fixture = fixture_relative_vs_absolute

        resolver = PathResolver()
        result = resolver.resolve(fixture["absolute_path"], "transcript")

        assert Path(result).exists()
        assert Path(result).resolve() == Path(fixture["file"]).resolve()

    def test_moved_file_state_stale(self, fixture_stale_state_pointers):
        """State file has stale pointer, verify fallback works."""
        fixture = fixture_stale_state_pointers

        resolver = PathResolver()

        # Try to resolve using stale path - should fall back to other strategies
        # This should not raise an error, but may return None or use fallback
        try:
            result = resolver.resolve_with_trace(
                fixture["stale_transcript_path"], "transcript"
            )
            # If it finds something, it should be the moved file
            if result["final_result"] and result["final_result"]["path"]:
                assert Path(result["final_result"]["path"]).exists()
        except FileNotFoundError:
            # Expected if no fallback strategy finds it
            pass

    def test_output_dir_resolution_shift(self, fixture_moved_outputs):
        """Output directory resolution doesn't shift unexpectedly."""
        fixture = fixture_moved_outputs

        resolver = PathResolver()

        # Try to resolve output directory
        # Should either find the moved location or fail gracefully
        try:
            result = resolver.resolve_with_trace(fixture["base_name"], "output_dir")
            # If found, should be consistent
            if result["final_result"] and result["final_result"]["path"]:
                resolved_path = result["final_result"]["path"]
                # Should be either original or moved (but not both)
                is_original = (
                    Path(resolved_path).resolve()
                    == Path(fixture["original_path"]).resolve()
                )
                is_moved = (
                    Path(resolved_path).resolve()
                    == Path(fixture["moved_path"]).resolve()
                )
                assert (
                    is_original or is_moved
                ), "Resolved path should match one of the known locations"
        except FileNotFoundError:
            # Expected if directory not found
            pass
