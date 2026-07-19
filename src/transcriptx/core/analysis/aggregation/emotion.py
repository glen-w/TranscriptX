"""
Group aggregation for emotion module.
"""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _extract_emotion_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    emotion_result = module_results.get("emotion", {})
    if not isinstance(emotion_result, dict):
        return {}
    payload = emotion_result.get("payload") or emotion_result.get("results") or {}
    return payload if isinstance(payload, dict) else {}


def _emotion_score_map(stats: Any) -> Dict[str, float]:
    """Normalize flat or lexical-v2 nested speaker/global emotion stats to floats.

    Lexical v2 stores profiles as::

        {"emotion_scores": {"joy": 0.1, ...}, "assignment_counts": {...}, ...}

    Legacy payloads were flat ``{"joy": 0.1, ...}``. Only numeric emotion
    scores are aggregated; nested dict metadata is ignored.
    """
    if not isinstance(stats, dict):
        return {}
    nested = stats.get("emotion_scores")
    src = nested if isinstance(nested, dict) else stats
    out: Dict[str, float] = {}
    for key, value in src.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[str(key)] = float(value)
    return out


def aggregate_emotion_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Aggregate per-transcript emotion results into group-level metrics.

    Returns None when emotion results are missing for all transcripts.
    """
    session_rows: List[Dict[str, Any]] = []
    speaker_aggregates: Dict[int, Dict[str, Any]] = {}

    for result in per_transcript_results:
        if "emotion" not in result.module_results:
            continue

        payload = _extract_emotion_payload(result.module_results)
        if not payload:
            continue

        speaker_stats = payload.get("speaker_stats", {})
        global_stats = _emotion_score_map(payload.get("global_stats", {}))
        if not isinstance(speaker_stats, dict):
            speaker_stats = {}
        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )

        for speaker, raw_scores in speaker_stats.items():
            scores = _emotion_score_map(raw_scores)
            if not scores:
                continue
            canonical_id = display_to_canonical.get(
                speaker, _fallback_canonical_id(speaker)
            )
            aggregate = speaker_aggregates.setdefault(
                canonical_id,
                {
                    "canonical_speaker_id": canonical_id,
                    "display_name": canonical_speaker_map.canonical_to_display.get(
                        canonical_id, speaker
                    ),
                    "appearance_count": 0,
                    "emotion_totals": {},
                },
            )
            aggregate["appearance_count"] += 1
            for emotion, value in scores.items():
                aggregate["emotion_totals"][emotion] = (
                    float(aggregate["emotion_totals"].get(emotion, 0.0)) + value
                )

        session_rows.append(
            session_row_from_result(
                result,
                transcript_set,
                run_id=result.run_id,
                global_emotions=global_stats,
                speaker_count=len(speaker_stats),
            )
        )

    if not session_rows:
        return None

    speaker_rows: List[Dict[str, Any]] = []
    for aggregate in speaker_aggregates.values():
        count = aggregate["appearance_count"] or 1
        averaged = {
            emotion: total / count
            for emotion, total in aggregate["emotion_totals"].items()
        }
        speaker_rows.append(
            {
                "canonical_speaker_id": aggregate["canonical_speaker_id"],
                "display_name": aggregate["display_name"],
                "appearance_count": aggregate["appearance_count"],
                "emotion_scores": averaged,
            }
        )

    session_rows.sort(key=lambda row: row["order_index"])

    # Unweighted mean of each transcript's global emotion profile (explicit pooled).
    emotion_keys: set[str] = set()
    for row in session_rows:
        ge = row.get("global_emotions")
        if isinstance(ge, dict):
            emotion_keys.update(ge.keys())
    scores: Dict[str, float] = {}
    for key in emotion_keys:
        vals = [
            float(row["global_emotions"][key])
            for row in session_rows
            if isinstance(row.get("global_emotions"), dict)
            and key in row["global_emotions"]
            and isinstance(row["global_emotions"][key], (int, float))
            and not isinstance(row["global_emotions"][key], bool)
        ]
        if vals:
            scores[key] = sum(vals) / len(vals)
    emotion_pooled = {"schema_version": 1, "emotion_scores": scores}

    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "emotion_pooled": emotion_pooled,
    }
