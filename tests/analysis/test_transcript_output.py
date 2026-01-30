"""
Tests for transcript output analysis module.

This module tests human-readable transcript generation.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.transcript_output import TranscriptOutputAnalysis


class TestTranscriptOutputAnalysis:
    """Tests for TranscriptOutputAnalysis."""
    
    @pytest.fixture
    def transcript_output_module(self):
        """Fixture for TranscriptOutputAnalysis instance."""
        return TranscriptOutputAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Hello, how are you?", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "I'm doing well, thanks!", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "That's great to hear.", "start": 4.0, "end": 6.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    def test_transcript_output_basic(self, transcript_output_module, sample_segments, sample_speaker_map):
        """Test basic transcript output generation."""
        result = transcript_output_module.analyze(sample_segments, sample_speaker_map)
        
        assert "segments" in result
        assert "speaker_map" in result
        assert "total_segments" in result
        assert result["total_segments"] == len(sample_segments)
    
    def test_transcript_output_empty_segments(self, transcript_output_module, sample_speaker_map):
        """Test transcript output with empty segments."""
        segments = []
        
        result = transcript_output_module.analyze(segments, sample_speaker_map)
        
        assert "segments" in result
        assert "total_segments" in result
        assert result["total_segments"] == 0
    
    @patch('transcriptx.core.utils.transcript_output.generate_human_friendly_transcript_from_file')
    def test_transcript_output_save_results(self, mock_generate, transcript_output_module, sample_segments, sample_speaker_map):
        """Test saving transcript output results."""
        mock_output_service = MagicMock()
        mock_output_service.transcript_path = "/tmp/test_transcript.json"
        
        result = transcript_output_module.analyze(sample_segments, sample_speaker_map)
        transcript_output_module._save_results(result, mock_output_service)
        
        # Should call generate function
        mock_generate.assert_called_once_with("/tmp/test_transcript.json")
