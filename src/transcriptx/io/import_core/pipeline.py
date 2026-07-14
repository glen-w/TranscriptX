"""Normalization pipeline stages for imported transcripts."""

from __future__ import annotations

from dataclasses import replace
from typing import List, Sequence, Tuple

from transcriptx.io.import_core.normalization_policy import NormalizationPolicy
from transcriptx.io.intermediate_transcript import (
    IntermediateTranscript,
    IntermediateTurn,
    TranscriptSegment,
)
from transcriptx.io.speaker_normalizer import normalize_speakers
from transcriptx.io.transcript_normalizer import TranscriptNormalizer


def run_normalization_pipeline(
    intermediate: IntermediateTranscript,
    policy: NormalizationPolicy,
) -> Tuple[List[TranscriptSegment], dict]:
    normalizer = TranscriptNormalizer(
        merge_same_speaker=policy.merge_adjacent_same_speaker,
        default_estimated_duration=policy.default_estimated_duration_s,
        gap_warning_threshold_s=policy.gap_warning_threshold_s,
    )
    turns = normalizer.normalize(intermediate)
    turns = _apply_turn_policies(turns, policy)
    segments = list(normalize_speakers(turns))
    if policy.sort_segments:
        segments.sort(
            key=lambda s: (float(s.get("start", 0.0)), float(s.get("end", 0.0)))
        )
    if policy.drop_zero_length_segments:
        segments = [s for s in segments if float(s["end"]) > float(s["start"])]
    if policy.dedupe_exact_duplicates:
        segments = _dedupe_segments(segments)

    actions = {
        "turns_in": len(intermediate.turns),
        "segments_out": len(segments),
        "warnings_total": len(intermediate.warnings),
    }
    return segments, actions


def _apply_turn_policies(
    turns: Sequence[IntermediateTurn],
    policy: NormalizationPolicy,
) -> List[IntermediateTurn]:
    if policy.preserve_empty_speaker_labels:
        return list(turns)
    updated: List[IntermediateTurn] = []
    for turn in turns:
        speaker = turn.speaker
        if speaker is not None and not speaker.strip():
            updated.append(replace(turn, speaker=None))
        else:
            updated.append(turn)
    return updated


def _dedupe_segments(segments: Sequence[TranscriptSegment]) -> List[TranscriptSegment]:
    seen = set()
    deduped: List[TranscriptSegment] = []
    for seg in segments:
        key = (
            float(seg["start"]),
            float(seg["end"]),
            str(seg["speaker"]),
            str(seg["text"]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(seg)
    return deduped
