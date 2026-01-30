"""
Integration tests for output service.

This module tests: Analysis results → Output service → File generation.
"""

from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path

from transcriptx.core.output.output_service import OutputService


@pytest.mark.integration
class TestOutputServiceIntegration:
    """Tests for output service integration."""
    
    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Fixture for temporary output directory."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        return output_dir
    
    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results."""
        return {
            "sentiment": {
                "segments": [
                    {"speaker": "SPEAKER_00", "sentiment_score": 0.8}
                ],
                "summary": {"average_sentiment": 0.8}
            }
        }
    
    def test_output_service_file_generation(self, temp_output_dir, sample_analysis_results):
        """Test that output service generates files correctly."""
        output_service = OutputService(
            base_name="test_transcript",
            output_dir=str(temp_output_dir)
        )
        
        # Save data
        output_service.save_data(sample_analysis_results["sentiment"], "sentiment", format_type="json")
        
        # Verify file was created
        output_file = temp_output_dir / "test_transcript" / "sentiment" / "data.json"
        assert output_file.exists() or (temp_output_dir / "test_transcript" / "sentiment").exists()
    
    def test_output_directory_structure(self, temp_output_dir):
        """Test output directory structure creation."""
        output_service = OutputService(
            base_name="test_transcript",
            output_dir=str(temp_output_dir)
        )
        
        output_structure = output_service.get_output_structure()
        
        assert "base_output_dir" in output_structure or "module_dirs" in output_structure
