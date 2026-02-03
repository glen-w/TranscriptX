"""
Voice analysis package for TranscriptX.

This package provides:
- Segment-level voice feature extraction (CPU-first; openSMILE eGeMAPS optional)
- On-disk caching keyed by audio + segment timing + config
- Aggregations for mismatch, tension curve, and speaker drift
"""

from .schema import (
    EGEMAPS_CANONICAL_FIELDS,
    VoiceFeatureRow,
    VoiceFeatureTable,
    resolve_segment_id,
)
from .extract import load_or_compute_voice_features

__all__ = [
    "VoiceFeatureRow",
    "VoiceFeatureTable",
    "EGEMAPS_CANONICAL_FIELDS",
    "resolve_segment_id",
    "load_or_compute_voice_features",
]

