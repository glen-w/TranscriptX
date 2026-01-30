"""
Tests for PipelineContext class.

This module tests the PipelineContext which holds all data needed during
pipeline execution and caches intermediate results.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline.pipeline_context import PipelineContext


class TestPipelineContext:
    """Tests for PipelineContext class."""
    
    def test_pipeline_context_initialization(
        self, temp_transcript_file, mock_transcript_service
    ):
        """Test PipelineContext initialization."""
        with patch('transcriptx.core.pipeline.pipeline_context.TranscriptService') as mock_service_class:
            mock_service_class.return_value = mock_transcript_service
            
            context = PipelineContext(
                transcript_path=str(temp_transcript_file),
                skip_speaker_mapping=True
            )
            
            assert context.transcript_path == str(temp_transcript_file)
            assert hasattr(context, 'speaker_map')  # Extracted from segments
            assert hasattr(context, 'segments')
            assert hasattr(context, 'base_name')
            assert hasattr(context, 'transcript_dir')
    
    def test_pipeline_context_get_segments(self, pipeline_context_factory):
        """Test getting segments from context."""
        context = pipeline_context_factory()
        
        segments = context.get_segments()
        
        assert isinstance(segments, list)
        assert len(segments) > 0
    
    def test_pipeline_context_get_speaker_map(self, pipeline_context_factory):
        """Test getting speaker map from context (extracted from segments)."""
        context = pipeline_context_factory()
        
        speaker_map = context.get_speaker_map()
        
        assert isinstance(speaker_map, dict)  # Extracted from segments
    
    def test_pipeline_context_get_base_name(self, pipeline_context_factory):
        """Test getting base name from context."""
        context = pipeline_context_factory()
        
        base_name = context.get_base_name()
        
        assert isinstance(base_name, str)
        assert len(base_name) > 0
    
    def test_pipeline_context_store_analysis_result(self, pipeline_context_factory):
        """Test storing analysis results in context."""
        context = pipeline_context_factory()
        
        test_result = {"module": "sentiment", "data": "test"}
        context.store_analysis_result("sentiment", test_result)
        
        stored_result = context.get_analysis_result("sentiment")
        assert stored_result == test_result
    
    def test_pipeline_context_get_analysis_result_nonexistent(self, pipeline_context_factory):
        """Test getting non-existent analysis result."""
        context = pipeline_context_factory()
        
        result = context.get_analysis_result("nonexistent")
        
        assert result is None
    
    def test_pipeline_context_store_computed_value(self, pipeline_context_factory):
        """Test storing computed values in context."""
        context = pipeline_context_factory()
        
        context.store_computed_value("test_key", "test_value")
        
        value = context.get_computed_value("test_key")
        assert value == "test_value"
    
    def test_pipeline_context_get_computed_value_nonexistent(self, pipeline_context_factory):
        """Test getting non-existent computed value."""
        context = pipeline_context_factory()
        
        value = context.get_computed_value("nonexistent")
        
        assert value is None
    
    def test_pipeline_context_has_computed_value(self, pipeline_context_factory):
        """Test checking if computed value exists."""
        context = pipeline_context_factory()
        
        assert context.has_computed_value("nonexistent") is False
        
        context.store_computed_value("existing", "value")
        assert context.has_computed_value("existing") is True
    
    def test_pipeline_context_speaker_map_extraction(self, pipeline_context_factory):
        """Test that speaker map is extracted from segments."""
        context = pipeline_context_factory()
        
        # Speaker map should be extracted from segments
        assert isinstance(context.speaker_map, dict)
    
    def test_pipeline_context_file_not_found(self, tmp_path):
        """Test PipelineContext with non-existent file."""
        non_existent_file = tmp_path / "nonexistent.json"
        
        with patch('transcriptx.core.pipeline.pipeline_context.TranscriptService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.load_transcript_data.side_effect = FileNotFoundError("File not found")
            mock_service_class.return_value = mock_service
            
            with pytest.raises(FileNotFoundError):
                PipelineContext(transcript_path=str(non_existent_file))
    
    def test_pipeline_context_invalid_transcript(self, temp_transcript_file):
        """Test PipelineContext with invalid transcript data."""
        with patch('transcriptx.core.pipeline.pipeline_context.TranscriptService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.load_transcript_data.side_effect = ValueError("Invalid data")
            mock_service_class.return_value = mock_service
            
            with pytest.raises(ValueError):
                PipelineContext(transcript_path=str(temp_transcript_file))
    
    def test_pipeline_context_batch_mode(self, pipeline_context_factory):
        """Test PipelineContext in batch mode."""
        context = pipeline_context_factory(batch_mode=True)
        
        # Should work the same way
        assert context.get_segments() is not None
    
    def test_pipeline_context_set_segments(self, pipeline_context_factory):
        """Test setting segments in context."""
        context = pipeline_context_factory()
        
        new_segments = [{"speaker": "SPEAKER_00", "text": "New segment", "start": 0.0, "end": 1.0}]
        context.set_segments(new_segments)
        
        assert context.get_segments() == new_segments
    
    def test_pipeline_context_get_transcript_service(self, pipeline_context_factory):
        """Test getting TranscriptService from context."""
        context = pipeline_context_factory()
        
        service = context.get_transcript_service()
        
        assert service is not None

    def test_pipeline_context_metadata_speaker_map(self, tmp_path, mock_transcript_service):
        """Test speaker map metadata influences display name resolution."""
        transcript_path = tmp_path / "test.json"
        transcript_path.write_text(
            '{"segments":[{"speaker":"SPEAKER_00","text":"Hello"}],"speaker_map":{"SPEAKER_00":"Alice"}}'
        )

        with patch('transcriptx.core.pipeline.pipeline_context.TranscriptService') as mock_service_class:
            mock_service_class.return_value = mock_transcript_service

            context = PipelineContext(
                transcript_path=str(transcript_path),
                skip_speaker_mapping=True,
                transcript_key="test_key",
                run_id="run123",
            )

            assert context.get_speaker_map() == {"SPEAKER_00": "Alice"}
            assert context.get_speaker_display_name("SPEAKER_00") == "Alice (SPEAKER_00)"

    def test_pipeline_context_close_clears_caches(self, pipeline_context_factory):
        """Test close clears cached data."""
        context = pipeline_context_factory()
        context.store_analysis_result("sentiment", {"ok": True})
        context.store_computed_value("key", "value")

        context.close()

        assert context._analysis_results == {}
        assert context._computed_values == {}
        assert context._closed is True

    def test_pipeline_context_close_idempotent(self, pipeline_context_factory):
        """Test close can be called multiple times safely."""
        context = pipeline_context_factory()
        context.close()
        context.close()
        assert context._closed is True
