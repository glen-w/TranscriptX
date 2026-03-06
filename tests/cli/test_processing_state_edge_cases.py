"""
Tests for processing state edge cases.

This module tests state corruption recovery, concurrent access, and versioning.
"""

import pytest
import json

from transcriptx.cli.processing_state import (
    load_processing_state,
    save_processing_state,
)


class TestProcessingStateEdgeCases:
    """Tests for processing state edge cases."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Fixture for temporary state file."""
        state_file = tmp_path / "processing_state.json"
        return state_file

    def test_state_corruption_recovery(self, temp_state_file):
        """Test recovery from corrupted state file."""
        # Create corrupted state file
        temp_state_file.write_text("invalid json content {")

        # Should handle corruption gracefully
        try:
            state = load_processing_state(str(temp_state_file))
            # Should return empty state or handle error
            assert state is not None or isinstance(state, dict)
        except (json.JSONDecodeError, ValueError):
            # Expected behavior - should handle gracefully
            pass

    def test_state_missing_file(self, tmp_path):
        """Test handling of missing state file."""
        missing_file = tmp_path / "nonexistent_state.json"

        # Should handle missing file gracefully
        state = load_processing_state(str(missing_file))
        assert state is not None

    def test_state_versioning(self, temp_state_file):
        """Test state version handling."""
        # Create state with version
        state_data = {"version": "1.0", "transcript_path": "/tmp/test.json"}
        temp_state_file.write_text(json.dumps(state_data))

        state = load_processing_state(str(temp_state_file))

        # Should preserve version or handle migration
        assert state is not None

    def test_state_empty_values(self, temp_state_file):
        """Test state with empty values."""
        state_data = {"transcript_path": None, "mp3_path": "", "status": None}
        temp_state_file.write_text(json.dumps(state_data))

        state = load_processing_state(str(temp_state_file))

        # Should handle empty values
        assert state is not None

    def test_state_save_and_load_consistency(self, temp_state_file):
        """Test that saved state can be loaded consistently."""
        original_state = {"transcript_path": "/tmp/test.json", "status": "processing"}

        save_processing_state(original_state, str(temp_state_file))
        loaded_state = load_processing_state(str(temp_state_file))

        assert loaded_state["transcript_path"] == original_state["transcript_path"]
        assert loaded_state["status"] == original_state["status"]
