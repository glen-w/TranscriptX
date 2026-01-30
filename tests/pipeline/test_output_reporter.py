"""
Tests for output reporter functionality.

This module tests output summary generation, formatting, and display.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline.output_reporter import OutputReporter


class TestOutputReporter:
    """Tests for OutputReporter class."""
    
    @pytest.fixture
    def output_reporter(self):
        """Fixture for OutputReporter instance."""
        return OutputReporter()
    
    @pytest.fixture
    def sample_transcript_path(self, tmp_path):
        """Fixture for sample transcript path."""
        transcript_file = tmp_path / "test_transcript.json"
        transcript_file.write_text('{"segments": []}')
        return str(transcript_file)
    
    def test_generate_comprehensive_output_summary_success(
        self, output_reporter, sample_transcript_path, tmp_path
    ):
        """Test successful output summary generation."""
        # Create output directory structure
        output_dir = tmp_path / "test_transcript"
        output_dir.mkdir()
        (output_dir / "sentiment").mkdir()
        (output_dir / "stats").mkdir()
        
        with patch('transcriptx.core.pipeline.output_reporter.get_transcript_dir', return_value=str(output_dir)), \
             patch('transcriptx.core.pipeline.output_reporter.validate_module_outputs') as mock_validate:
            
            mock_validate.return_value = {
                "sentiment": {"valid": True},
                "stats": {"valid": True}
            }
            
            summary = output_reporter.generate_comprehensive_output_summary(
                transcript_path=sample_transcript_path,
                selected_modules=["sentiment", "stats"],
                modules_run=["sentiment", "stats"],
                errors=[]
            )
        
        assert "transcript_info" in summary
        assert "analysis_summary" in summary
        assert "outputs" in summary
        assert summary["analysis_summary"]["total_modules_successful"] == 2
    
    def test_generate_comprehensive_output_summary_with_errors(
        self, output_reporter, sample_transcript_path, tmp_path
    ):
        """Test output summary generation with errors."""
        output_dir = tmp_path / "test_transcript"
        output_dir.mkdir()
        
        with patch('transcriptx.core.pipeline.output_reporter.get_transcript_dir', return_value=str(output_dir)), \
             patch('transcriptx.core.pipeline.output_reporter.validate_module_outputs') as mock_validate:
            
            mock_validate.return_value = {}
            
            summary = output_reporter.generate_comprehensive_output_summary(
                transcript_path=sample_transcript_path,
                selected_modules=["sentiment", "stats"],
                modules_run=["sentiment"],
                errors=["Error in stats module"]
            )
        
        assert summary["analysis_summary"]["total_modules_failed"] == 1
        assert len(summary["analysis_summary"]["errors"]) == 1
    
    def test_generate_comprehensive_output_summary_no_output_dir(
        self, output_reporter, sample_transcript_path, tmp_path
    ):
        """Test output summary when output directory doesn't exist."""
        with patch('transcriptx.core.pipeline.output_reporter.get_transcript_dir', return_value=str(tmp_path / "missing_dir")):
            summary = output_reporter.generate_comprehensive_output_summary(
                transcript_path=sample_transcript_path,
                selected_modules=["sentiment"],
                modules_run=["sentiment"],
                errors=[]
            )
        
        assert "error" in summary["outputs"]
        assert "does not exist" in summary["outputs"]["error"]
    
    def test_display_output_summary_to_user(
        self, output_reporter, sample_transcript_path
    ):
        """Test displaying output summary to user."""
        summary = {
            "transcript_info": {"base_name": "test"},
            "analysis_summary": {
                "total_modules_successful": 2,
                "total_modules_failed": 0
            }
        }
        
        with patch('transcriptx.core.pipeline.output_reporter.console.print') as mock_print:
            output_reporter.display_output_summary_to_user(summary)
        
        # Should display summary
        assert mock_print.called
    
    def test_validate_module_outputs_integration(
        self, output_reporter, sample_transcript_path, tmp_path
    ):
        """Test output validation integration."""
        output_dir = tmp_path / "test_transcript"
        output_dir.mkdir()
        (output_dir / "sentiment").mkdir()
        (output_dir / "sentiment" / "test_transcript_sentiment.json").write_text('{}')
        
        with patch('transcriptx.core.pipeline.output_reporter.get_transcript_dir', return_value=str(output_dir)), \
             patch('transcriptx.core.pipeline.output_reporter.validate_module_outputs') as mock_validate:
            
            mock_validate.return_value = {
                "sentiment": {"valid": True, "files": ["test_transcript_sentiment.json"]}
            }
            
            summary = output_reporter.generate_comprehensive_output_summary(
                transcript_path=sample_transcript_path,
                selected_modules=["sentiment"],
                modules_run=["sentiment"],
                errors=[]
            )
        
        assert "validation" in summary
        assert "sentiment" in summary["validation"]
