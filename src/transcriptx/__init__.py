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
- Database backend for persistent speaker profiling and cross-session tracking
- Docker support for dependency-free deployment

Package Structure:
- core/: Main analysis modules and pipeline orchestration
- cli/: Command-line interface with interactive features
- database/: Database operations, speaker profiling, and cross-session tracking
- utils/: Utility functions and helper modules
- preprocessing/: Data preprocessing and configuration files

"""

__version__ = "0.42"
