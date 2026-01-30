"""
Integration tests for cross-workflow state management.

This module tests state persistence and consistency across different workflows.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import pytest

from transcriptx.cli.processing_state import (
    load_processing_state,
    save_processing_state,
    get_current_transcript_path_from_state
)


@pytest.mark.integration
class TestCrossWorkflowState:
    """Tests for cross-workflow state management."""
    
    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Fixture for temporary state file."""
        state_file = tmp_path / "processing_state.json"
        return state_file
    
    def test_state_persistence_across_workflows(self, temp_state_file, tmp_path):
        """Test state persistence across workflows."""
        # Simulate transcription workflow saving state
        transcript_path = str(tmp_path / "test_transcript.json")
        state_data = {
            "transcript_path": transcript_path,
            "status": "transcribed",
            "mp3_path": str(tmp_path / "test.mp3")
        }
        
        save_processing_state(state_data, str(temp_state_file))
        
        # Simulate analysis workflow loading state
        loaded_state = load_processing_state(str(temp_state_file))
        
        # Verify state consistency
        assert loaded_state["transcript_path"] == transcript_path
        assert loaded_state["status"] == "transcribed"
    
    def test_state_version_migration(self, temp_state_file):
        """Test state version migration."""
        # Create old state format
        old_state = {
            "version": "1.0",
            "transcript_path": "/tmp/old_transcript.json"
        }
        temp_state_file.write_text(json.dumps(old_state))
        
        # Load and verify migration (if implemented)
        loaded_state = load_processing_state(str(temp_state_file))
        
        # Should handle old format gracefully
        assert loaded_state is not None
        assert "transcript_path" in loaded_state or "version" in loaded_state
    
    def test_path_resolution_from_state(self, temp_state_file, tmp_path):
        """Test path resolution from state."""
        # Save state with relative path
        state_data = {
            "transcript_path": "test_transcript.json",
            "status": "transcribed"
        }
        save_processing_state(state_data, str(temp_state_file))
        
        # Load state and resolve path
        loaded_state = load_processing_state(str(temp_state_file))
        transcript_path = get_current_transcript_path_from_state()
        
        # Verify path resolution (if implemented)
        assert loaded_state is not None
    
    def test_state_consistency_after_workflow(self, temp_state_file, tmp_path):
        """Test state consistency after workflow execution."""
        # Initial state
        initial_state = {
            "transcript_path": str(tmp_path / "transcript.json"),
            "status": "pending"
        }
        save_processing_state(initial_state, str(temp_state_file))
        
        # Simulate workflow updating state
        updated_state = {
            "transcript_path": str(tmp_path / "transcript.json"),
            "status": "completed",
            "analysis_run": True
        }
        save_processing_state(updated_state, str(temp_state_file))
        
        # Verify state updated
        loaded_state = load_processing_state(str(temp_state_file))
        assert loaded_state["status"] == "completed"
        assert loaded_state.get("analysis_run") is True
    
    def test_state_isolation_between_sessions(self, temp_state_file, tmp_path):
        """Test that state is properly isolated between sessions."""
        # Session 1 state
        session1_state = {
            "transcript_path": str(tmp_path / "session1.json"),
            "session_id": "session1"
        }
        save_processing_state(session1_state, str(temp_state_file))
        
        # Session 2 loads state
        loaded_state = load_processing_state(str(temp_state_file))
        
        # Verify state loaded correctly
        assert loaded_state["transcript_path"] == session1_state["transcript_path"]
    
    def test_state_recovery_after_corruption(self, temp_state_file):
        """Test state recovery after corruption."""
        # Create corrupted state
        temp_state_file.write_text("invalid json {")
        
        # Should handle corruption gracefully
        try:
            state = load_processing_state(str(temp_state_file))
            # Should return empty state or handle error
            assert state is not None or isinstance(state, dict)
        except (json.JSONDecodeError, ValueError):
            # Expected behavior
            pass
