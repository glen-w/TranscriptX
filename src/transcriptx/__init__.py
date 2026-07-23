"""
TranscriptX - Modular Transcript Analysis Toolkit

A comprehensive toolkit for analyzing conversation transcripts with advanced NLP capabilities.
This package provides modular analysis components for sentiment analysis, emotion detection,
dialogue act classification, speaker interactions, named entity recognition, and more.

Key Features:
- Multi-modal transcript analysis (sentiment, emotion, dialogue acts, etc.)
- Speaker interaction analysis (interruptions, networks, conversation loops)
- Named Entity Recognition with geocoding capabilities
- Topic modeling and semantic similarity analysis
- Configurable analysis pipelines with DAG dependency management
- Quality filtering and intelligent segment selection
- Docker support for dependency-free deployment

Package structure (high level):
- web/: Streamlit GUI entrypoint (`transcriptx` console script)
- app/: Workflows and request/response models for the GUI and Python API
- core/: Pipeline, analysis modules, domain, and internal utilities
- io/: Transcript loading, adapters, import/canonicalization
- services/: Shared application services (e.g. speaker studio)
- utils/: Cross-cutting helpers (HTML, errors, etc.)
- preprocessing/: Static resources (stopwords, lexicon data)
"""

__version__ = "0.7.0"
