"""
Analysis module for TranscriptX core functionality.

This module contains all analysis-related components including:
- ACTS (Automated Conversation Tracking System)
- Sentiment and emotion analysis
- NER (Named Entity Recognition)
- Topic modeling
- Semantic similarity analysis
- Statistics and wordclouds
- Tics analysis
"""

from __future__ import annotations

import importlib
from typing import List

_lazy_modules = {
    "acts",
    "conversation_loops",
    "contagion",
    "entity_sentiment",
    "interactions",
    "emotion",
    "ner",
    "semantic_similarity",
    "sentiment",
    "stats",
    "topic_modeling",
    "understandability",
    "wordclouds",
    "tics",
    "temporal_dynamics",
    "qa_analysis",
    "dynamics",
    "highlights",
    "summary",
}


def __getattr__(name: str):
    if name in _lazy_modules:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_lazy_modules))


__all__ = [
    # ACTS and conversation analysis
    "acts",
    "conversation_loops",
    "contagion",
    "entity_sentiment",
    "interactions",
    # Core analysis components
    "emotion",
    "ner",
    "semantic_similarity",
    "sentiment",
    "stats",
    "topic_modeling",
    "understandability",
    "wordclouds",
    "tics",
    # Temporal and Q&A analysis
    "temporal_dynamics",
    "qa_analysis",
    "dynamics",
    # Highlights and summary
    "highlights",
    "summary",
]
