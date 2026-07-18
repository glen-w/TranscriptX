"""
Lexical emotion data merging for contagion analysis.

Only the lexical branch (nrc_emotion from the `emotion` module) is merged
here. The contextual branch is merged via
transcriptx.core.analysis.emotion_family.consumer_contracts.merge_contextual_projection,
which enforces provenance (context_emotion_source == 'contextual_emotion').
Legacy provenance-less context_emotion_* fields are UI/report-only and must
never be propagated into contagion inputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash


def _has_positive_scores(data: Any) -> bool:
    return isinstance(data, dict) and any(
        isinstance(v, (int, float)) and v > 0 for v in data.values()
    )


def merge_lexical_emotion(
    segments: List[Dict[str, Any]],
    source_segments: List[Dict[str, Any]],
    logger: Any,
    tolerance: float = 0.5,
) -> int:
    """
    Copy nrc_emotion from producer segments into consumer segments.

    Matches by unique segment id and requires emotion_scored_text_hash.
    Timestamp fallback is retained only when both sides carry a matching hash.
    Returns the number of segments that received nrc_emotion.
    """
    if not source_segments:
        logger.debug("merge_lexical_emotion: source_segments is empty")
        return 0

    by_id: Dict[str, Mapping[str, Any]] = {}
    by_start: List[tuple[float, Mapping[str, Any]]] = []
    for src in source_segments:
        if not _has_positive_scores(src.get("nrc_emotion")):
            continue
        expected = src.get("emotion_scored_text_hash")
        if not expected:
            continue
        sid = src.get("id") or src.get("segment_id")
        if sid is not None and str(sid).strip():
            by_id[str(sid)] = src
        start = src.get("start")
        if isinstance(start, (int, float)):
            by_start.append((float(start), src))

    merged_count = 0
    for seg in segments:
        if _has_positive_scores(seg.get("nrc_emotion")):
            expected = seg.get("emotion_scored_text_hash")
            if not expected or expected != segment_text_hash(seg.get("text")):
                for key in (
                    "nrc_emotion",
                    "nrc_valence_scores",
                    "nrc_emotion_coverage",
                    "emotion_evaluation_state",
                    "emotion_scored_text_hash",
                    "emotion_canonical_ref",
                ):
                    seg.pop(key, None)
                continue
            merged_count += 1
            continue

        src: Optional[Mapping[str, Any]] = None
        sid = seg.get("id") or seg.get("segment_id")
        if sid is not None:
            src = by_id.get(str(sid))
        if src is None:
            seg_start = seg.get("start")
            if isinstance(seg_start, (int, float)):
                for cand_start, cand in by_start:
                    if abs(float(seg_start) - cand_start) < tolerance:
                        src = cand
                        break
        if src is None:
            continue
        expected = src.get("emotion_scored_text_hash")
        if not expected or expected != segment_text_hash(seg.get("text")):
            continue

        seg["nrc_emotion"] = dict(src["nrc_emotion"])
        if "emotion_scored_text_hash" in src:
            seg["emotion_scored_text_hash"] = src["emotion_scored_text_hash"]
        if "emotion_canonical_ref" in src:
            seg["emotion_canonical_ref"] = src["emotion_canonical_ref"]
        if "emotion_evaluation_state" in src:
            seg["emotion_evaluation_state"] = src["emotion_evaluation_state"]
        merged_count += 1

    logger.debug(
        f"merge_lexical_emotion: {merged_count}/{len(segments)} segments carry nrc_emotion"
    )
    return merged_count
