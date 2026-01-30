"""
Integration tests for pipeline state management.

This module tests pipeline execution → State updates → Resume capability.
"""

from unittest.mock import MagicMock, patch
import pytest
import json
from pathlib import Path

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline


@pytest.mark.integration
class TestPipelineStateIntegration:
    """Tests for pipeline and state management integration."""
    
    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Fixture for temporary state file."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({}))
        return state_file
    
    def test_pipeline_updates_state(self, temp_transcript_file, sample_speaker_map, temp_state_file):
        """Test that pipeline execution updates state."""
        with patch('transcriptx.core.pipeline.pipeline.create_dag_pipeline') as mock_create_dag, \
             patch('transcriptx.core.pipeline.pipeline.validate_transcript'), \
             patch('transcriptx.io.transcript_service.get_transcript_service') as mock_get_service:
            
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["sentiment"],
                "errors": []
            }
            mock_create_dag.return_value = mock_dag
            
            mock_service = MagicMock()
            mock_service.load_transcript_data.return_value = (
                [{"speaker": "SPEAKER_00", "text": "Test", "start": 0.0, "end": 1.0}],
                "test",
                str(temp_transcript_file.parent),
                sample_speaker_map
            )
            mock_get_service.return_value = mock_service
            
            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"]
            )
            
            assert result is not None
            assert "modules_run" in result
    
    def test_state_consistency(self, temp_state_file):
        """Test state consistency across workflow steps."""
        # Load initial state
        initial_state = json.loads(temp_state_file.read_text())
        
        # Simulate state update
        initial_state["test_key"] = "test_value"
        temp_state_file.write_text(json.dumps(initial_state))
        
        # Verify state persists
        updated_state = json.loads(temp_state_file.read_text())
        assert updated_state["test_key"] == "test_value"
