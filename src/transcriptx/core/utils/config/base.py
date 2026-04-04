"""Shared configuration constants."""

from __future__ import annotations

from pathlib import Path

# Emotion categories for analysis
# These are the standard emotion categories used by the emotion detection models
EMOTION_CATEGORIES = [
    "anger",
    "anticipation",
    "disgust",
    "fear",
    "joy",
    "negative",
    "positive",
    "sadness",
    "surprise",
    "trust",
]

# Dialogue act types
# These are the conversation acts that can be classified in dialogue analysis
ACT_TYPES = [
    "question",
    "suggestion",
    "agreement",
    "disagreement",
    "gratitude",
    "statement",
]

# Default NER labels to extract
# These are the named entity types that will be identified in text
DEFAULT_NER_LABELS = ["PERSON", "ORG", "GPE", "LOC", "DATE", "TIME", "MONEY"]

# Word cloud stopwords
# Common words that are typically excluded from word cloud generation
DEFAULT_STOPWORDS = [
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "can",
    "this",
    "that",
    "these",
    "those",
]

# File paths for preprocessing data
# These paths point to configuration files used by various analysis modules
_PREPROCESSING_ROOT = (
    Path(__file__).resolve().parents[3] / "preprocessing" / "stopwords"
)
STOPWORDS_FILE = _PREPROCESSING_ROOT / "stopwords.json"
TICS_FILE = _PREPROCESSING_ROOT / "verbal_tics.json"
DISCOURSE_STOPLIST_FILE = _PREPROCESSING_ROOT / "discourse_stoplist.json"
