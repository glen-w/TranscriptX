"""Normalization policy for import pipelines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizationPolicy:
    sort_segments: bool = True
    dedupe_exact_duplicates: bool = False
    merge_adjacent_same_speaker: bool = False
    drop_zero_length_segments: bool = True
    preserve_empty_speaker_labels: bool = False
    gap_warning_threshold_s: float = 30.0
    default_estimated_duration_s: float = 5.0
