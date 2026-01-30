"""
Tests for audio fingerprinting utilities.

This module tests audio fingerprinting functions for content-based duplicate detection.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import numpy as np
import pytest

pytestmark = pytest.mark.unit

from transcriptx.cli.audio_fingerprinting import (
    compute_audio_fingerprint,
    compare_audio_files,
    batch_compare_audio_group,
    clear_fingerprint_cache,
    is_librosa_available,
)


class TestComputeAudioFingerprint:
    """Tests for compute_audio_fingerprint function."""
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', False)
    def test_compute_fingerprint_librosa_not_available(self, tmp_path):
        """Test when librosa is not available."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"fake audio")
        
        result = compute_audio_fingerprint(file_path)
        
        assert result is None
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', True)
    @patch('transcriptx.cli.audio_fingerprinting.librosa')
    def test_compute_fingerprint_success(self, mock_librosa, tmp_path):
        """Test successful fingerprint computation."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"fake audio")
        
        # Mock librosa.load
        mock_audio = np.random.rand(22050)  # 1 second of audio
        mock_librosa.load.return_value = (mock_audio, 22050)
        
        # Mock chroma_cqt
        mock_chroma = np.random.rand(12, 100)  # 12 chroma bins, 100 frames
        mock_librosa.feature.chroma_cqt.return_value = mock_chroma
        
        result = compute_audio_fingerprint(file_path)
        
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert len(result) == 12  # 12 chroma bins
        mock_librosa.load.assert_called_once()
        mock_librosa.feature.chroma_cqt.assert_called_once()
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', True)
    @patch('transcriptx.cli.audio_fingerprinting.librosa')
    def test_compute_fingerprint_too_short(self, mock_librosa, tmp_path):
        """Test when audio file is too short."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"fake audio")
        
        # Mock very short audio (less than 0.1 seconds)
        mock_audio = np.random.rand(1000)  # Less than 0.1 seconds at 22050 Hz
        mock_librosa.load.return_value = (mock_audio, 22050)
        
        result = compute_audio_fingerprint(file_path)
        
        assert result is None
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', True)
    @patch('transcriptx.cli.audio_fingerprinting.librosa')
    def test_compute_fingerprint_caching(self, mock_librosa, tmp_path):
        """Test that fingerprints are cached."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"fake audio")
        
        # Mock librosa
        mock_audio = np.random.rand(22050)
        mock_librosa.load.return_value = (mock_audio, 22050)
        mock_chroma = np.random.rand(12, 100)
        mock_librosa.feature.chroma_cqt.return_value = mock_chroma
        
        # Clear cache first
        clear_fingerprint_cache()
        
        # First call
        result1 = compute_audio_fingerprint(file_path)
        
        # Second call should use cache
        result2 = compute_audio_fingerprint(file_path)
        
        # Should only call librosa once (cached on second call)
        assert mock_librosa.load.call_count == 1
        assert result1 is not None
        assert result2 is not None
        np.testing.assert_array_equal(result1, result2)
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', True)
    @patch('transcriptx.cli.audio_fingerprinting.librosa')
    def test_compute_fingerprint_error_handling(self, mock_librosa, tmp_path):
        """Test error handling when librosa fails."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"fake audio")
        
        # Mock librosa.load to raise exception
        mock_librosa.load.side_effect = Exception("Load failed")
        
        result = compute_audio_fingerprint(file_path)
        
        assert result is None


class TestCompareAudioFiles:
    """Tests for compare_audio_files function."""
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', False)
    def test_compare_files_librosa_not_available(self, tmp_path):
        """Test when librosa is not available."""
        file1 = tmp_path / "file1.mp3"
        file2 = tmp_path / "file2.mp3"
        file1.write_bytes(b"audio1")
        file2.write_bytes(b"audio2")
        
        is_dup, similarity = compare_audio_files(file1, file2)
        
        assert is_dup is False
        assert similarity == 0.0
    
    @patch('transcriptx.cli.audio_fingerprinting.compute_audio_fingerprint')
    def test_compare_files_identical(self, mock_compute, tmp_path):
        """Test comparing identical files."""
        file1 = tmp_path / "file1.mp3"
        file2 = tmp_path / "file2.mp3"
        file1.write_bytes(b"audio1")
        file2.write_bytes(b"audio2")
        
        # Mock identical fingerprints
        fingerprint = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        mock_compute.return_value = fingerprint
        
        is_dup, similarity = compare_audio_files(file1, file2, threshold=0.90)
        
        assert is_dup is True
        assert similarity == 1.0  # Identical fingerprints
    
    @patch('transcriptx.cli.audio_fingerprinting.compute_audio_fingerprint')
    def test_compare_files_different(self, mock_compute, tmp_path):
        """Test comparing different files."""
        file1 = tmp_path / "file1.mp3"
        file2 = tmp_path / "file2.mp3"
        file1.write_bytes(b"audio1")
        file2.write_bytes(b"audio2")
        
        # Mock different fingerprints
        fingerprint1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        fingerprint2 = np.array([-1.0, -2.0, -3.0, -4.0, -5.0, -6.0, -7.0, -8.0, -9.0, -10.0, -11.0, -12.0])
        mock_compute.side_effect = [fingerprint1, fingerprint2]
        
        is_dup, similarity = compare_audio_files(file1, file2, threshold=0.90)
        
        assert is_dup is False
        assert similarity < 0.90
    
    @patch('transcriptx.cli.audio_fingerprinting.compute_audio_fingerprint')
    def test_compare_files_fingerprint_fails(self, mock_compute, tmp_path):
        """Test when fingerprint computation fails."""
        file1 = tmp_path / "file1.mp3"
        file2 = tmp_path / "file2.mp3"
        file1.write_bytes(b"audio1")
        file2.write_bytes(b"audio2")
        
        # Mock fingerprint failure
        mock_compute.return_value = None
        
        is_dup, similarity = compare_audio_files(file1, file2)
        
        assert is_dup is False
        assert similarity == 0.0


class TestBatchCompareAudioGroup:
    """Tests for batch_compare_audio_group function."""
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', False)
    def test_batch_compare_librosa_not_available(self, tmp_path):
        """Test when librosa is not available."""
        files = [tmp_path / f"file{i}.mp3" for i in range(3)]
        for f in files:
            f.write_bytes(b"audio")
        
        result = batch_compare_audio_group(files)
        
        assert result == {}
    
    @patch('transcriptx.cli.audio_fingerprinting.compare_audio_files')
    def test_batch_compare_finds_duplicates(self, mock_compare, tmp_path):
        """Test finding duplicates in a group."""
        files = [tmp_path / f"file{i}.mp3" for i in range(3)]
        for f in files:
            f.write_bytes(b"audio")
        
        # Mock comparisons:
        # file0 vs file1: duplicates (similarity 0.95)
        # file0 vs file2: not duplicates (similarity 0.50)
        # file1 vs file2: not duplicates (similarity 0.50)
        def compare_side_effect(f1, f2, **kwargs):
            if (f1 == files[0] and f2 == files[1]) or (f1 == files[1] and f2 == files[0]):
                return True, 0.95
            return False, 0.50
        
        mock_compare.side_effect = compare_side_effect
        
        result = batch_compare_audio_group(files, threshold=0.90)
        
        # Should find file0 and file1 as duplicates
        assert len(result) > 0
        # Check that file0 and file1 are grouped together
        found_group = False
        for group in result.values():
            if files[0] in group and files[1] in group:
                found_group = True
                break
        assert found_group
    
    @patch('transcriptx.cli.audio_fingerprinting.compare_audio_files')
    def test_batch_compare_no_duplicates(self, mock_compare, tmp_path):
        """Test when no duplicates are found."""
        files = [tmp_path / f"file{i}.mp3" for i in range(3)]
        for f in files:
            f.write_bytes(b"audio")
        
        # Mock all comparisons as not duplicates
        mock_compare.return_value = (False, 0.50)
        
        result = batch_compare_audio_group(files, threshold=0.90)
        
        assert result == {}
    
    def test_batch_compare_insufficient_files(self, tmp_path):
        """Test with less than 2 files."""
        files = [tmp_path / "file1.mp3"]
        files[0].write_bytes(b"audio")
        
        result = batch_compare_audio_group(files)
        
        assert result == {}


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_clear_fingerprint_cache(self, tmp_path):
        """Test clearing fingerprint cache."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"audio")
        
        # Add something to cache (if cache is accessible)
        # This is mainly to ensure the function doesn't crash
        clear_fingerprint_cache()
        
        # Function should complete without error
        assert True
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', True)
    def test_is_librosa_available_true(self):
        """Test is_librosa_available when available."""
        assert is_librosa_available() is True
    
    @patch('transcriptx.cli.audio_fingerprinting.LIBROSA_AVAILABLE', False)
    def test_is_librosa_available_false(self):
        """Test is_librosa_available when not available."""
        assert is_librosa_available() is False
