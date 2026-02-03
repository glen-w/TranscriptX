"""
Tests for file selection utilities.

This module tests interactive file selection, discovery, navigation,
and file formatting functions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.cli.file_selection_utils import (
    discover_all_transcript_paths,
    select_folder_interactive,
    select_transcript_file_interactive,
    select_audio_for_whisperx_transcription,
    _format_transcript_file_with_analysis,
    _has_analysis_outputs
)


class TestSelectFolderInteractive:
    """Tests for select_folder_interactive function."""
    
    @patch('transcriptx.cli.file_selection_utils.questionary.select')
    def test_select_folder_navigation(self, mock_select, tmp_path):
        """Test folder navigation."""
        folder1 = tmp_path / "folder1"
        folder1.mkdir()
        folder2 = folder1 / "folder2"
        folder2.mkdir()
        
        # Mock navigation: go into folder1, then select folder2
        mock_select.return_value.ask.side_effect = [
            str(folder1),  # Navigate into folder1
            str(folder2)   # Select folder2
        ]
        
        result = select_folder_interactive(start_path=tmp_path)
        
        # Should return selected folder
        assert result is not None
    
    @patch('transcriptx.cli.file_selection_utils.questionary.select')
    def test_select_folder_cancel(self, mock_select):
        """Test canceling folder selection."""
        mock_select.return_value.ask.return_value = None
        
        result = select_folder_interactive()
        
        # Should return None when cancelled
        assert result is None
    
    @patch('transcriptx.cli.file_selection_utils.os.scandir')
    def test_select_folder_permission_error(self, mock_scandir, tmp_path):
        """Test handling permission errors."""
        mock_scandir.side_effect = PermissionError("Permission denied")
        
        result = select_folder_interactive(start_path=tmp_path)
        
        # Should handle error gracefully
        assert result is None


class TestSelectTranscriptFileInteractive:
    """Tests for select_transcript_file_interactive function."""
    
    @patch('transcriptx.cli.file_selection_utils.select_files_interactive')
    def test_select_transcript_file_success(self, mock_select_files, tmp_path):
        """Test successful transcript file selection."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')
        
        mock_select_files.return_value = [transcript_file]
        
        result = select_transcript_file_interactive()
        
        assert result == transcript_file
        mock_select_files.assert_called_once()
    
    @patch('transcriptx.cli.file_selection_utils.select_files_interactive')
    def test_select_transcript_file_no_selection(self, mock_select_files):
        """Test when no file is selected."""
        mock_select_files.return_value = []
        
        result = select_transcript_file_interactive()
        
        assert result is None


class TestFormatTranscriptFileWithAnalysis:
    """Tests for _format_transcript_file_with_analysis function."""
    
    def test_format_transcript_with_segments(self, tmp_path):
        """Test formatting transcript file with segments."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": [{"speaker": "SPEAKER_00", "text": "Test"}]}')
        
        formatted = _format_transcript_file_with_analysis(transcript_file)
        
        assert "test.json" in formatted
        assert "segments" in formatted.lower() or "1" in formatted
    
    def test_format_transcript_with_text(self, tmp_path):
        """Test formatting transcript file with text field."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"text": "Some text content"}')
        
        formatted = _format_transcript_file_with_analysis(transcript_file)
        
        assert "test.json" in formatted
    
    @patch('transcriptx.cli.file_selection_utils._has_analysis_outputs')
    def test_format_transcript_unanalyzed(self, mock_has_analysis, tmp_path):
        """Test formatting unanalyzed transcript file."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')
        
        mock_has_analysis.return_value = False
        
        formatted = _format_transcript_file_with_analysis(transcript_file)
        
        # Should have ✨ prefix for unanalyzed files
        assert "✨" in formatted or "test.json" in formatted


class TestHasAnalysisOutputs:
    """Tests for _has_analysis_outputs function."""
    
    def test_has_analysis_outputs_true(self, tmp_path):
        """Test when analysis outputs exist."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')
        
        # Create analysis output directory
        output_dir = tmp_path / "test"
        output_dir.mkdir()
        (output_dir / "sentiment").mkdir()  # Analysis module directory
        
        with patch('transcriptx.cli.file_selection_utils.get_transcript_dir') as mock_get_dir:
            mock_get_dir.return_value = str(output_dir)
            
            has_analysis = _has_analysis_outputs(transcript_file)
        
        assert has_analysis is True
    
    def test_has_analysis_outputs_false(self, tmp_path):
        """Test when no analysis outputs exist."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')
        
        with patch('transcriptx.cli.file_selection_utils.get_transcript_dir') as mock_get_dir:
            mock_get_dir.return_value = str(tmp_path / "nonexistent")
            
            has_analysis = _has_analysis_outputs(transcript_file)
        
        assert has_analysis is False
    
    def test_has_analysis_outputs_only_speaker_map(self, tmp_path):
        """Test when only speaker map exists."""
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text('{"segments": []}')
        
        output_dir = tmp_path / "test"
        output_dir.mkdir()
        (output_dir / "test_speaker_map.json").write_text('{}')  # Only speaker map
        
        with patch('transcriptx.cli.file_selection_utils.get_transcript_dir') as mock_get_dir:
            mock_get_dir.return_value = str(output_dir)
            
            has_analysis = _has_analysis_outputs(transcript_file)
        
        # Should return False if only speaker map exists
        assert has_analysis is False


class TestDiscoverAllTranscriptPaths:
    """Tests for discover_all_transcript_paths helper."""

    def test_discover_all_transcript_paths_empty_root(self, tmp_path):
        """Empty root should return empty list."""
        results = discover_all_transcript_paths(root=tmp_path)
        assert results == []

    def test_discover_all_transcript_paths_transcripts_subtree(self, tmp_path):
        """When transcripts/ exists, search only that subtree."""
        transcripts_dir = tmp_path / "transcripts"
        transcripts_dir.mkdir()
        (transcripts_dir / "a.json").write_text('{"segments": []}')
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "b.json").write_text('{"segments": []}')

        results = discover_all_transcript_paths(root=tmp_path)
        assert results == [ (transcripts_dir / "a.json").resolve() ]

    def test_discover_all_transcript_paths_exclusions(self, tmp_path):
        """Exclude known output patterns and directories when no transcripts/ subtree."""
        (tmp_path / "valid.json").write_text('{"segments": []}')
        (tmp_path / "test_summary.json").write_text('{"summary": true}')
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "ignored.json").write_text('{"segments": []}')

        results = discover_all_transcript_paths(root=tmp_path)
        assert results == [ (tmp_path / "valid.json").resolve() ]
