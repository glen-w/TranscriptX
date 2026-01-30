"""
Tests for database integration pipeline.

This module tests DatabaseIntegrationPipeline.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.integration.database_pipeline import DatabaseIntegrationPipeline


class TestDatabaseIntegrationPipeline:
    """Tests for DatabaseIntegrationPipeline."""
    
    @pytest.fixture
    def pipeline(self):
        """Fixture for DatabaseIntegrationPipeline instance."""
        mock_session = MagicMock()
        return DatabaseIntegrationPipeline(database_session=mock_session)
    
    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results."""
        return {
            "sentiment": {
                "segments": [
                    {"speaker": "SPEAKER_00", "sentiment_score": 0.8}
                ]
            },
            "emotion": {
                "segments": [
                    {"speaker": "SPEAKER_00", "dominant_emotion": "joy"}
                ]
            }
        }
    
    def test_pipeline_initialization(self, pipeline):
        """Test pipeline initialization."""
        assert pipeline is not None
        assert hasattr(pipeline, 'extractors')
        assert hasattr(pipeline, 'profile_aggregator')
        assert hasattr(pipeline, 'persistence_service')
        assert hasattr(pipeline, 'error_handler')
    
    def test_process_analysis_results_basic(self, pipeline, sample_analysis_results):
        """Test basic processing of analysis results."""
        with patch.object(pipeline, '_validate_input_data'), \
             patch.object(pipeline, '_process_speaker_data') as mock_process, \
             patch.object(pipeline.profile_aggregator, 'aggregate_profiles'):
            
            mock_process.return_value = {"status": "success"}
            
            result = pipeline.process_analysis_results(
                sample_analysis_results,
                conversation_id=1,
                speaker_ids=[1, 2]
            )
            
            assert "conversation_id" in result
            assert "speakers_processed" in result
            assert "speakers_failed" in result
    
    def test_process_analysis_results_validation_error(self, pipeline, sample_analysis_results):
        """Test processing with validation error."""
        with patch.object(pipeline, '_validate_input_data') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid input")
            
            with pytest.raises(ValueError):
                pipeline.process_analysis_results(
                    sample_analysis_results,
                    conversation_id=1,
                    speaker_ids=[1]
                )
    
    def test_process_speaker_data(self, pipeline, sample_analysis_results):
        """Test processing data for a single speaker."""
        with patch.object(pipeline.extractors['sentiment'], 'extract_speaker_data') as mock_extract, \
             patch.object(pipeline.persistence_service, 'store_speaker_data') as mock_store:
            
            mock_extract.return_value = {"average_sentiment_score": 0.8}
            mock_store.return_value = True
            
            result = pipeline._process_speaker_data(
                sample_analysis_results,
                conversation_id=1,
                speaker_id=1
            )
            
            assert "speaker_id" in result
            assert "analysis_types_processed" in result
