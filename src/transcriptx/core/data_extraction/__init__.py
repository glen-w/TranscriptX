"""
Data extraction services for TranscriptX.

This module provides services to extract speaker-level data from analysis results
and transform it for database storage. Each analysis type has its own extractor
that implements the BaseDataExtractor interface.

Available Extractors:
- SentimentDataExtractor: Extracts sentiment analysis data
- EmotionDataExtractor: Extracts emotion analysis data
- TopicDataExtractor: Extracts topic modeling data
- EntityDataExtractor: Extracts NER analysis data
- TicDataExtractor: Extracts verbal tics data
- SemanticDataExtractor: Extracts semantic similarity data
- InteractionDataExtractor: Extracts interaction analysis data
- PerformanceDataExtractor: Extracts performance analysis data
"""

from .base_extractor import BaseDataExtractor
from .sentiment_extractor import SentimentDataExtractor
from .emotion_extractor import EmotionDataExtractor
from .topic_extractor import TopicDataExtractor
from .entity_extractor import EntityDataExtractor
from .tic_extractor import TicDataExtractor
from .semantic_extractor import SemanticDataExtractor
from .interaction_extractor import InteractionDataExtractor
from .performance_extractor import PerformanceDataExtractor
from .validation import DataValidationError, validate_speaker_data

__all__ = [
    "BaseDataExtractor",
    "SentimentDataExtractor",
    "EmotionDataExtractor",
    "TopicDataExtractor",
    "EntityDataExtractor",
    "TicDataExtractor",
    "SemanticDataExtractor",
    "InteractionDataExtractor",
    "PerformanceDataExtractor",
    "DataValidationError",
    "validate_speaker_data",
]
