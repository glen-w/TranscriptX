"""
Tests for file discovery utilities.

This module tests file discovery, metadata extraction, and filtering functions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.file_discovery import (
    discover_wav_files,
    filter_new_files,
    filter_files_by_size,
    find_duplicate_files_by_size,
    find_duplicate_files_by_size_and_content
)


class TestDiscoverWAVFiles:
    """Tests for discover_wav_files function."""
    
    def test_discover_wav_files_success(self, tmp_path):
        """Test discovering WAV files in folder."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        
        (folder / "file1.wav").write_bytes(b"wav data")
        (folder / "file2.wav").write_bytes(b"wav data")
        (folder / "file.txt").write_text("not wav")
        (folder / ".hidden.wav").write_bytes(b"hidden")  # Should be ignored
        
        files = discover_wav_files(folder)
        
        assert len(files) == 2
        assert all(f.suffix.lower() == ".wav" for f in files)
        assert all(not f.name.startswith(".") for f in files)
    
    def test_discover_wav_files_empty(self, tmp_path):
        """Test discovering files in empty folder."""
        folder = tmp_path / "empty"
        folder.mkdir()
        
        files = discover_wav_files(folder)
        
        assert len(files) == 0
    
    def test_discover_wav_files_case_insensitive(self, tmp_path):
        """Test that discovery is case-insensitive for extensions."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        
        (folder / "file1.WAV").write_bytes(b"wav data")
        (folder / "file2.wav").write_bytes(b"wav data")
        
        files = discover_wav_files(folder)
        
        assert len(files) == 2


class TestFilterNewFiles:
    """Tests for filter_new_files function."""
    
    @patch('transcriptx.cli.file_discovery.load_processing_state')
    @patch('transcriptx.cli.file_discovery.is_file_processed')
    def test_filter_new_files_all_new(
        self, mock_is_processed, mock_load_state, tmp_path
    ):
        """Test filtering when all files are new."""
        files = [tmp_path / "file1.wav", tmp_path / "file2.wav"]
        for f in files:
            f.write_bytes(b"wav")
        
        mock_load_state.return_value = {}
        mock_is_processed.return_value = False
        
        new_files = filter_new_files(files)
        
        assert len(new_files) == 2
        assert set(new_files) == set(files)
    
    @patch('transcriptx.cli.file_discovery.load_processing_state')
    @patch('transcriptx.cli.file_discovery.is_file_processed')
    def test_filter_new_files_all_processed(
        self, mock_is_processed, mock_load_state, tmp_path
    ):
        """Test filtering when all files are processed."""
        files = [tmp_path / "file1.wav"]
        files[0].write_bytes(b"wav")
        
        mock_load_state.return_value = {}
        mock_is_processed.return_value = True
        
        new_files = filter_new_files(files)
        
        assert len(new_files) == 0
    
    @patch('transcriptx.cli.file_discovery.load_processing_state')
    @patch('transcriptx.cli.file_discovery.is_file_processed')
    def test_filter_new_files_mixed(
        self, mock_is_processed, mock_load_state, tmp_path
    ):
        """Test filtering with mix of processed and new files."""
        files = [tmp_path / "file1.wav", tmp_path / "file2.wav"]
        for f in files:
            f.write_bytes(b"wav")
        
        mock_load_state.return_value = {}
        mock_is_processed.side_effect = [True, False]  # First processed, second new
        
        new_files = filter_new_files(files)
        
        assert len(new_files) == 1
        assert new_files[0] == files[1]


class TestFilterFilesBySize:
    """Tests for filter_files_by_size function."""
    
    def test_filter_files_by_min_size(self, tmp_path):
        """Test filtering by minimum size."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        
        # Create files with different sizes
        small_file = folder / "small.wav"
        small_file.write_bytes(b"x" * (10 * 1024 * 1024))  # 10 MB
        
        large_file = folder / "large.wav"
        large_file.write_bytes(b"x" * (50 * 1024 * 1024))  # 50 MB
        
        files = [small_file, large_file]
        filtered = filter_files_by_size(files, min_size_mb=30)
        
        assert len(filtered) == 1
        assert filtered[0] == large_file
    
    def test_filter_files_by_max_size(self, tmp_path):
        """Test filtering by maximum size."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        
        small_file = folder / "small.wav"
        small_file.write_bytes(b"x" * (10 * 1024 * 1024))  # 10 MB
        
        large_file = folder / "large.wav"
        large_file.write_bytes(b"x" * (50 * 1024 * 1024))  # 50 MB
        
        files = [small_file, large_file]
        filtered = filter_files_by_size(files, max_size_mb=30)
        
        assert len(filtered) == 1
        assert filtered[0] == small_file
    
    def test_filter_files_by_size_range(self, tmp_path):
        """Test filtering by size range."""
        folder = tmp_path / "wavs"
        folder.mkdir()
        
        small_file = folder / "small.wav"
        small_file.write_bytes(b"x" * (10 * 1024 * 1024))  # 10 MB
        
        medium_file = folder / "medium.wav"
        medium_file.write_bytes(b"x" * (25 * 1024 * 1024))  # 25 MB
        
        large_file = folder / "large.wav"
        large_file.write_bytes(b"x" * (50 * 1024 * 1024))  # 50 MB
        
        files = [small_file, medium_file, large_file]
        filtered = filter_files_by_size(files, min_size_mb=20, max_size_mb=40)
        
        assert len(filtered) == 1
        assert filtered[0] == medium_file


class TestFindDuplicateFilesBySize:
    """Tests for find_duplicate_files_by_size function."""
    
    def test_find_duplicates_by_size(self, tmp_path):
        """Test finding duplicate files by size."""
        folder = tmp_path / "files"
        folder.mkdir()
        
        # Create files with same size (duplicates)
        file1 = folder / "file1.txt"
        file2 = folder / "file2.txt"
        file3 = folder / "file3.txt"
        
        content = b"same content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        file3.write_bytes(b"different")  # Different size
        
        files = [file1, file2, file3]
        duplicates = find_duplicate_files_by_size(files)
        
        # Should find duplicates (file1 and file2 have same size)
        assert len(duplicates) > 0
        # The size of content should be in duplicates
        size = len(content)
        assert size in duplicates
        assert len(duplicates[size]) == 2
    
    def test_find_duplicates_no_duplicates(self, tmp_path):
        """Test when no duplicates exist."""
        folder = tmp_path / "files"
        folder.mkdir()
        
        file1 = folder / "file1.txt"
        file2 = folder / "file2.txt"
        
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")
        
        files = [file1, file2]
        duplicates = find_duplicate_files_by_size(files)
        
        # Should return empty dict
        assert len(duplicates) == 0


class TestFindDuplicateFilesBySizeAndContent:
    """Tests for find_duplicate_files_by_size_and_content function."""
    
    @patch('transcriptx.cli.audio_fingerprinting.is_librosa_available')
    @patch('transcriptx.cli.audio_fingerprinting.batch_compare_audio_group')
    @patch('transcriptx.cli.file_discovery._is_audio_file')
    def test_find_duplicates_with_content_comparison(
        self, mock_is_audio, mock_batch_compare, mock_librosa_available, tmp_path
    ):
        """Test finding duplicates with content-based comparison."""
        folder = tmp_path / "files"
        folder.mkdir()
        
        # Create files with same size
        file1 = folder / "file1.mp3"
        file2 = folder / "file2.mp3"
        file3 = folder / "file3.txt"
        
        content = b"same content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        file3.write_bytes(content)
        
        files = [file1, file2, file3]
        
        # Mock librosa as available
        mock_librosa_available.return_value = True
        
        # Mock audio file detection
        mock_is_audio.side_effect = lambda f: f.suffix == '.mp3'
        
        # Mock content comparison: file1 and file2 are duplicates
        mock_batch_compare.return_value = {
            file1: [file1, file2]  # file1 and file2 are duplicates
        }
        
        duplicates = find_duplicate_files_by_size_and_content(files, threshold=0.90)
        
        # Should find duplicates
        assert len(duplicates) > 0
        size = len(content)
        assert size in duplicates
        # Should include both audio duplicates and non-audio files with same size
        assert len(duplicates[size]) >= 2
    
    @patch('transcriptx.cli.audio_fingerprinting.is_librosa_available')
    def test_find_duplicates_fallback_to_size_only(
        self, mock_librosa_available, tmp_path
    ):
        """Test fallback to size-only when librosa is not available."""
        folder = tmp_path / "files"
        folder.mkdir()
        
        file1 = folder / "file1.txt"
        file2 = folder / "file2.txt"
        
        content = b"same content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        files = [file1, file2]
        
        # Mock librosa as not available
        mock_librosa_available.return_value = False
        
        duplicates = find_duplicate_files_by_size_and_content(files)
        
        # Should still find duplicates by size
        assert len(duplicates) > 0
        size = len(content)
        assert size in duplicates
        assert len(duplicates[size]) == 2
    
    @patch('transcriptx.cli.audio_fingerprinting.is_librosa_available')
    @patch('transcriptx.cli.audio_fingerprinting.batch_compare_audio_group')
    @patch('transcriptx.cli.file_discovery._is_audio_file')
    def test_find_duplicates_no_content_matches(
        self, mock_is_audio, mock_batch_compare, mock_librosa_available, tmp_path
    ):
        """Test when files have same size but different content."""
        folder = tmp_path / "files"
        folder.mkdir()
        
        file1 = folder / "file1.mp3"
        file2 = folder / "file2.mp3"
        
        content = b"same size content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        files = [file1, file2]
        
        # Mock librosa as available
        mock_librosa_available.return_value = True
        mock_is_audio.return_value = True
        
        # Mock content comparison: no duplicates (different content)
        mock_batch_compare.return_value = {}  # No duplicates found
        
        duplicates = find_duplicate_files_by_size_and_content(files, threshold=0.90)
        
        # Should return empty (no content matches)
        assert len(duplicates) == 0
