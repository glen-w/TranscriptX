"""
Tests for deduplication workflow implementation.

This module tests duplicate detection and removal including file discovery,
duplicate grouping, and interactive file selection for deletion.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.deduplication_workflow import (
    _run_deduplication_workflow_impl,
    _discover_all_files,
    _precompute_file_metadata,
    _review_duplicate_group
)


class TestDeduplicationWorkflowImpl:
    """Tests for _run_deduplication_workflow_impl function."""
    
    @patch('transcriptx.cli.deduplication_workflow.select_folder_interactive')
    @patch('transcriptx.cli.deduplication_workflow._discover_all_files')
    @patch('transcriptx.cli.audio_fingerprinting.is_librosa_available')
    @patch('transcriptx.cli.deduplication_workflow.find_duplicate_files_by_size_and_content')
    @patch('transcriptx.cli.deduplication_workflow.find_duplicate_files_by_size')
    def test_deduplication_workflow_no_duplicates(
        self, mock_find_by_size, mock_find_by_content, mock_librosa_available,
        mock_discover, mock_select_folder, tmp_path
    ):
        """Test workflow when no duplicates found."""
        folder = tmp_path / "files"
        folder.mkdir()
        
        mock_select_folder.return_value = folder
        mock_discover.return_value = [folder / "file1.txt", folder / "file2.txt"]
        mock_librosa_available.return_value = False  # Use size-only detection
        mock_find_by_size.return_value = {}  # No duplicates
        
        with patch('transcriptx.cli.deduplication_workflow.print'):
            _run_deduplication_workflow_impl()
        
        mock_select_folder.assert_called_once()
        mock_discover.assert_called_once()
        mock_find_by_size.assert_called_once()
        mock_find_by_content.assert_not_called()
    
    @patch('transcriptx.cli.deduplication_workflow.select_folder_interactive')
    @patch('transcriptx.cli.deduplication_workflow._discover_all_files')
    @patch('transcriptx.cli.audio_fingerprinting.is_librosa_available')
    @patch('transcriptx.cli.deduplication_workflow.find_duplicate_files_by_size_and_content')
    @patch('transcriptx.cli.deduplication_workflow.find_duplicate_files_by_size')
    @patch('transcriptx.cli.deduplication_workflow._review_duplicate_group')
    @patch('transcriptx.cli.deduplication_workflow.questionary.confirm')
    def test_deduplication_workflow_with_duplicates(
        self, mock_confirm, mock_review, mock_find_by_size,
        mock_find_by_content, mock_librosa_available,
        mock_discover, mock_select_folder, tmp_path
    ):
        """Test workflow with duplicates found."""
        folder = tmp_path / "files"
        folder.mkdir()
        file1 = folder / "file1.txt"
        file2 = folder / "file2.txt"
        file1.write_bytes(b"same content")
        file2.write_bytes(b"same content")
        
        mock_select_folder.return_value = folder
        mock_discover.return_value = [file1, file2]
        mock_librosa_available.return_value = False  # Use size-only detection
        mock_find_by_size.return_value = {
            13: [file1, file2]  # Same size
        }
        mock_review.return_value = []  # No files deleted
        mock_confirm.return_value.ask.return_value = False  # Don't continue
        
        with patch('transcriptx.cli.deduplication_workflow.print'):
            _run_deduplication_workflow_impl()
        
        mock_find_by_size.assert_called_once()
        mock_find_by_content.assert_not_called()
        mock_review.assert_called_once()
    
    @patch('transcriptx.cli.deduplication_workflow.select_folder_interactive')
    def test_deduplication_workflow_no_folder(self, mock_select_folder):
        """Test when no folder is selected."""
        mock_select_folder.return_value = None
        
        _run_deduplication_workflow_impl()
        
        # Should return early
        mock_select_folder.assert_called_once()
    
    @patch('transcriptx.cli.deduplication_workflow.select_folder_interactive')
    @patch('transcriptx.cli.deduplication_workflow._discover_all_files')
    def test_deduplication_workflow_no_files(
        self, mock_discover, mock_select_folder, tmp_path
    ):
        """Test when no files found."""
        folder = tmp_path / "empty"
        folder.mkdir()
        
        mock_select_folder.return_value = folder
        mock_discover.return_value = []
        
        with patch('transcriptx.cli.deduplication_workflow.print'):
            _run_deduplication_workflow_impl()
        
        # Should handle empty folder
        mock_discover.assert_called_once()


class TestDiscoverAllFiles:
    """Tests for _discover_all_files function."""
    
    def test_discover_all_files_success(self, tmp_path):
        """Test discovering files in folder."""
        folder = tmp_path / "test"
        folder.mkdir()
        
        (folder / "file1.txt").write_text("content1")
        (folder / "file2.txt").write_text("content2")
        (folder / ".hidden").write_text("hidden")  # Should be ignored
        
        files = _discover_all_files(folder)
        
        assert len(files) == 2
        assert all(f.name in ["file1.txt", "file2.txt"] for f in files)
    
    def test_discover_all_files_empty(self, tmp_path):
        """Test discovering files in empty folder."""
        folder = tmp_path / "empty"
        folder.mkdir()
        
        files = _discover_all_files(folder)
        
        assert len(files) == 0
    
    def test_discover_all_files_nonexistent(self, tmp_path):
        """Test discovering files in non-existent folder."""
        nonexistent = tmp_path / "nonexistent"
        
        files = _discover_all_files(nonexistent)
        
        # Should handle error gracefully
        assert isinstance(files, list)


class TestPrecomputeFileMetadata:
    """Tests for _precompute_file_metadata function."""
    
    @patch('transcriptx.cli.deduplication_workflow._is_audio_file')
    @patch('transcriptx.cli.deduplication_workflow.get_audio_duration')
    def test_precompute_metadata_audio_files(
        self, mock_duration, mock_is_audio, tmp_path
    ):
        """Test precomputing metadata for audio files."""
        files = [tmp_path / "audio.mp3"]
        files[0].write_bytes(b"fake audio")
        
        mock_is_audio.return_value = True
        mock_duration.return_value = 120.0
        
        metadata = _precompute_file_metadata(files)
        
        assert len(metadata) == 1
        assert "size_mb" in metadata[files[0]]
        assert "duration" in metadata[files[0]]
    
    def test_precompute_metadata_regular_files(self, tmp_path):
        """Test precomputing metadata for regular files."""
        files = [tmp_path / "file.txt"]
        files[0].write_text("content")
        
        with patch('transcriptx.cli.deduplication_workflow._is_audio_file', return_value=False):
            metadata = _precompute_file_metadata(files)
        
        assert len(metadata) == 1
        assert "size_mb" in metadata[files[0]]
        assert "duration" not in metadata[files[0]]


class TestReviewDuplicateGroup:
    """Tests for _review_duplicate_group function."""
    
    @patch('transcriptx.cli.deduplication_workflow.select_files_interactive')
    @patch('transcriptx.cli.deduplication_workflow.questionary.confirm')
    def test_review_duplicate_group_no_selection(
        self, mock_confirm, mock_select, tmp_path
    ):
        """Test reviewing duplicate group with no files selected."""
        files = [tmp_path / "file1.txt", tmp_path / "file2.txt"]
        for f in files:
            f.write_text("content")
        
        mock_select.return_value = []  # No files selected
        
        deleted = _review_duplicate_group(files, 100, 1, 1, tmp_path)
        
        assert len(deleted) == 0
        mock_select.assert_called_once()
    
    @patch('transcriptx.cli.deduplication_workflow.select_files_interactive')
    @patch('transcriptx.cli.deduplication_workflow.questionary.confirm')
    def test_review_duplicate_group_user_cancels(
        self, mock_confirm, mock_select, tmp_path
    ):
        """Test when user cancels deletion."""
        files = [tmp_path / "file1.txt"]
        files[0].write_text("content")
        
        mock_select.return_value = files
        mock_confirm.return_value.ask.return_value = False  # Cancel deletion
        
        deleted = _review_duplicate_group(files, 100, 1, 1, tmp_path)
        
        assert len(deleted) == 0
        mock_confirm.assert_called_once()
    
    @patch('transcriptx.cli.deduplication_workflow.select_files_interactive')
    @patch('transcriptx.cli.deduplication_workflow.questionary.confirm')
    def test_review_duplicate_group_deletes_files(
        self, mock_confirm, mock_select, tmp_path
    ):
        """Test deleting files from duplicate group."""
        files = [tmp_path / "file1.txt", tmp_path / "file2.txt"]
        for f in files:
            f.write_text("content")
        
        mock_select.return_value = [files[0]]  # Select first file
        mock_confirm.return_value.ask.return_value = True  # Confirm deletion
        
        deleted = _review_duplicate_group(files, 100, 1, 1, tmp_path)
        
        # Should delete selected file
        assert len(deleted) == 1
        assert deleted[0] == files[0]
