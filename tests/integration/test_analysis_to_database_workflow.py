"""
Integration tests for analysis to database workflow.

This module tests the complete workflow: Analysis pipeline → Data extraction → Database storage.
"""

from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.integration.database_pipeline import DatabaseIntegrationPipeline


@pytest.mark.integration
class TestAnalysisToDatabaseWorkflow:
    """Tests for analysis to database integration workflow."""
    
    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results."""
        return {
            "sentiment": {
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "I love this!",
                        "sentiment_score": 0.8,
                        "sentiment_label": "positive"
                    }
                ]
            },
            "emotion": {
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "I'm so happy!",
                        "dominant_emotion": "joy"
                    }
                ]
            }
        }
    
    @pytest.fixture
    def mock_database_session(self):
        """Fixture for mock database session."""
        return MagicMock()
    
    def test_complete_workflow(self, sample_analysis_results, mock_database_session):
        """Test complete workflow from analysis to database."""
        pipeline = DatabaseIntegrationPipeline(database_session=mock_database_session)
        
        with patch.object(pipeline, '_validate_input_data'), \
             patch.object(pipeline, '_process_speaker_data') as mock_process, \
             patch.object(pipeline.profile_aggregator, 'aggregate_profiles') as mock_aggregate:
            
            mock_process.return_value = {
                "speaker_id": 1,
                "analysis_types_processed": ["sentiment", "emotion"]
            }
            mock_aggregate.return_value = {"status": "success"}
            
            result = pipeline.process_analysis_results(
                sample_analysis_results,
                conversation_id=1,
                speaker_ids=[1]
            )
            
            assert result["speakers_processed"] > 0
            mock_aggregate.assert_called_once()
    
    def test_workflow_with_multiple_speakers(self, sample_analysis_results, mock_database_session):
        """Test workflow with multiple speakers."""
        pipeline = DatabaseIntegrationPipeline(database_session=mock_database_session)
        
        with patch.object(pipeline, '_validate_input_data'), \
             patch.object(pipeline, '_process_speaker_data') as mock_process, \
             patch.object(pipeline.profile_aggregator, 'aggregate_profiles'):
            
            mock_process.return_value = {"speaker_id": 1, "analysis_types_processed": []}
            
            result = pipeline.process_analysis_results(
                sample_analysis_results,
                conversation_id=1,
                speaker_ids=[1, 2]
            )
            
            assert mock_process.call_count == 2
            assert result["speakers_processed"] == 2
    
    def test_workflow_error_handling(self, sample_analysis_results, mock_database_session):
        """Test workflow error handling."""
        pipeline = DatabaseIntegrationPipeline(database_session=mock_database_session)
        
        with patch.object(pipeline, '_validate_input_data'), \
             patch.object(pipeline, '_process_speaker_data') as mock_process:
            
            mock_process.side_effect = Exception("Processing error")
            
            result = pipeline.process_analysis_results(
                sample_analysis_results,
                conversation_id=1,
                speaker_ids=[1]
            )
            
            assert result["speakers_failed"] > 0
            assert len(result["errors"]) > 0
