"""
Core analysis modules for TranscriptX.

This package contains all the main analysis modules for transcript processing.
The modules are organized into submodules for better maintainability:
- analysis: All analysis components (ACTS, sentiment, NER, etc.)
- pipeline: Pipeline orchestration and management
- utils: Configuration, logging, and utility functions

The modules are designed to be modular and can be run independently or as part
of a coordinated pipeline.

Available Analysis Modules:
- acts: Dialogue act classification (questions, statements, agreements, etc.)
- emotion: Emotion detection using transformer models
- interactions: Speaker interaction analysis (interruptions, networks)
- ner: Named Entity Recognition with geocoding
- sentiment: Sentiment analysis using VADER
- stats: Summary statistics and metrics
- topic_modeling: Topic modeling using LDA and NMF
- semantic_similarity: Semantic similarity and repetition detection
- conversation_loops: Detection of conversation patterns and loops
- entity_sentiment: Entity-focused sentiment analysis
- contagion: Emotional contagion detection
- wordclouds: Word cloud generation with various approaches
- transcript_output: Human-readable transcript generation

"""

# Import config module (always available)
from .utils import config

# Import pipeline functions
from .pipeline.module_registry import get_available_modules, get_default_modules
from .pipeline.pipeline import run_analysis_pipeline

# Define the public API for this package
__all__ = [
    # Config
    "config",
    # Pipeline
    "run_analysis_pipeline",
    "get_available_modules",
    "get_default_modules",
]
