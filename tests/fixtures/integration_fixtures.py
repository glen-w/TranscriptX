"""
Fixtures for integration tests.

This module provides fixtures for complete workflows and integration testing.
"""

from pathlib import Path
from unittest.mock import MagicMock
import json
import pytest

from transcriptx.core.pipeline.pipeline_context import PipelineContext


@pytest.fixture
def complete_analysis_results():
    """Fixture for complete analysis results from multiple modules."""
    return {
        "sentiment": {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I love this!",
                    "sentiment_score": 0.8,
                    "sentiment_label": "positive"
                }
            ],
            "summary": {"average_sentiment": 0.8}
        },
        "emotion": {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "I'm so happy!",
                    "dominant_emotion": "joy",
                    "emotion_scores": {"joy": 0.9}
                }
            ]
        },
        "ner": {
            "entities": [
                {"text": "Python", "type": "ORG", "start": 10, "end": 16}
            ]
        }
    }


@pytest.fixture
def mock_database_session():
    """Fixture for mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.commit.return_value = None
    session.rollback.return_value = None
    return session


@pytest.fixture
def workflow_context(temp_transcript_file):
    """
    Fixture for complete workflow context.
    
    Note: speaker_map parameter is deprecated. PipelineContext now extracts
    speaker information directly from segments using database-driven approach.
    """
    return PipelineContext(
        transcript_path=str(temp_transcript_file),
        skip_speaker_mapping=True
    )


@pytest.fixture
def mock_whisperx_service():
    """Fixture for mock WhisperX service."""
    service = MagicMock()
    service.transcribe.return_value = {
        "transcript_path": "/tmp/test_transcript.json",
        "status": "success"
    }
    return service
