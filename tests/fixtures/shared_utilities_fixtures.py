"""
Fixtures for shared utilities testing.

This module provides reusable fixtures for testing shared utilities
(similarity_utils, base_extractor, output_builder).
"""

from pathlib import Path

import pytest

from transcriptx.core.utils.similarity_utils import SimilarityCalculator
from transcriptx.core.data_extraction.base_extractor import BaseDataExtractor
from transcriptx.core.utils.output_builder import OutputStructureBuilder


# Concrete extractor for testing
class TestDataExtractor(BaseDataExtractor):
    """Test data extractor implementation."""
    def extract_data(self, analysis_results, speaker_id):
        return {"test_field": "test_value", "score": 0.8}
    def get_required_fields(self):
        return ["test_field"]


@pytest.fixture
def similarity_calculator_instance():
    """Create a SimilarityCalculator instance."""
    return SimilarityCalculator()


@pytest.fixture
def test_data_extractor():
    """Create a test data extractor."""
    return TestDataExtractor("test_module")


@pytest.fixture
def output_structure_builder():
    """Create an OutputStructureBuilder instance."""
    return OutputStructureBuilder("test_module")


@pytest.fixture
def sample_texts():
    """Create sample texts for similarity testing."""
    return [
        "Python is a great programming language",
        "I love Python programming",
        "Python makes coding fun",
        "Java is also a programming language"
    ]


@pytest.fixture
def sample_dictionaries():
    """Create sample dictionaries for similarity testing."""
    return {
        "dict1": {"a": 1, "b": 2, "c": 3},
        "dict2": {"a": 1, "b": 3, "d": 4},
        "dict3": {"x": 10, "y": 20}
    }


@pytest.fixture
def sample_behavioral_fingerprints():
    """Create sample behavioral fingerprints."""
    return {
        "fingerprint1": {
            "vocabulary_patterns": {"python": 10, "coding": 5},
            "speech_patterns": {"average_speaking_rate": 150, "average_segment_duration": 3.5},
            "emotion_patterns": {"joy": 0.7, "sadness": 0.1},
            "sentiment_patterns": {"average_sentiment": 0.6}
        },
        "fingerprint2": {
            "vocabulary_patterns": {"python": 8, "coding": 6},
            "speech_patterns": {"average_speaking_rate": 145, "average_segment_duration": 3.2},
            "emotion_patterns": {"joy": 0.65, "sadness": 0.15},
            "sentiment_patterns": {"average_sentiment": 0.55}
        }
    }


@pytest.fixture
def sample_speaker_data():
    """Create sample speaker data for extractor testing."""
    return {
        "SPEAKER_00": {
            "data": {"field1": "value1", "score": 0.8},
            "quality_metrics": {
                "completeness": 1.0,
                "consistency": 0.9,
                "validity": 1.0
            },
            "metadata": {"data_size": 100}
        },
        "SPEAKER_01": {
            "data": {"field1": "value2", "score": 0.6},
            "quality_metrics": {
                "completeness": 0.8,
                "consistency": 0.85,
                "validity": 0.9
            },
            "metadata": {"data_size": 150}
        }
    }


@pytest.fixture
def sample_output_structure(tmp_path):
    """Create a sample output structure."""
    transcript_path = str(tmp_path / "test.json")
    builder = OutputStructureBuilder("test_module")
    return builder.create_standard_output_structure(
        transcript_path, base_output_dir=str(tmp_path)
    )


@pytest.fixture
def sample_analysis_results():
    """Create sample analysis results."""
    return {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 2.0},
            {"speaker": "SPEAKER_01", "text": "Hi there", "start": 2.5, "end": 4.0}
        ],
        "metadata": {
            "transcript_path": "/path/to/transcript.json",
            "speaker_map": {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
        }
    }
