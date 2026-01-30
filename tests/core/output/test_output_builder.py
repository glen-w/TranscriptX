"""
Tests for output builder functionality.

This module tests output structure creation and path resolution.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    OutputStructure,
    save_global_chart,
    save_speaker_chart
)


class TestOutputStructure:
    """Tests for OutputStructure creation."""
    
    def test_create_standard_output_structure(self, tmp_path):
        """Test creating standard output structure."""
        transcript_dir = tmp_path / "test_transcript"
        module_name = "sentiment"
        
        structure = create_standard_output_structure(str(transcript_dir), module_name)
        
        assert structure is not None
        assert structure.data_dir is not None
        assert structure.global_data_dir is not None
        assert structure.charts_dir is not None
    
    def test_output_structure_directories_exist(self, tmp_path):
        """Test that output structure directories are created."""
        transcript_dir = tmp_path / "test_transcript"
        transcript_dir.mkdir()
        module_name = "sentiment"
        
        structure = create_standard_output_structure(str(transcript_dir), module_name)
        
        # Directories should exist or be created on first use
        assert structure.data_dir is not None
        assert structure.global_data_dir is not None


class TestSaveCharts:
    """Tests for chart saving functions."""
    
    def test_save_global_chart(self, tmp_path):
        """Test saving global chart."""
        transcript_dir = tmp_path / "test_transcript"
        transcript_dir.mkdir()
        charts_dir = transcript_dir / "charts" / "global"
        charts_dir.mkdir(parents=True)
        
        chart_data = MagicMock()
        base_name = "test"
        chart_name = "test_chart"
        
        with patch('transcriptx.core.utils.output_standards.plt') as mock_plt:
            file_path = save_global_chart(
                chart_data, str(charts_dir), base_name, chart_name
            )
        
        # Should return file path
        assert file_path is not None
    
    def test_save_speaker_chart(self, tmp_path):
        """Test saving speaker chart."""
        transcript_dir = tmp_path / "test_transcript"
        transcript_dir.mkdir()
        charts_dir = transcript_dir / "charts" / "speakers"
        charts_dir.mkdir(parents=True)
        
        chart_data = MagicMock()
        base_name = "test"
        chart_name = "test_chart"
        speaker_id = "SPEAKER_00"
        
        with patch('transcriptx.core.utils.output_standards.plt') as mock_plt:
            file_path = save_speaker_chart(
                chart_data, str(charts_dir), base_name, chart_name, speaker_id
            )
        
        # Should return file path with speaker ID
        assert file_path is not None
        assert speaker_id in file_path
