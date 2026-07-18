"""
Contagion detection utilities.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple


def _top_positive_label(scores: Dict[str, Any]) -> str | None:
    numeric = {
        k: v
        for k, v in scores.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
    }
    if not numeric:
        return None
    return max(numeric.items(), key=lambda x: x[1])[0]


def _resolve_context_emotion_label(seg: Dict[str, Any]) -> str | None:
    """
    Resolve a contagious contextual label, or None when the segment is ineligible.

    Labeled ``neutral`` (scored analytical_outcome) is eligible.
    Abstained / empty / no-label / failed outcomes are not contagious.
    """
    if seg.get("context_emotion_source") != "contextual_emotion":
        return None
    outcome = seg.get("contextual_emotion_analytical_outcome")
    if outcome in {"abstained", "failed", "skipped", "empty"}:
        return None
    if outcome == "neutral":
        return "neutral"
    label = (
        seg.get("contextual_emotion_label") or seg.get("context_emotion_primary") or ""
    )
    if isinstance(label, str) and label.strip():
        return str(label)
    raw = seg.get("context_emotion")
    if isinstance(raw, dict):
        return _top_positive_label(raw)
    if isinstance(raw, str) and raw.strip():
        return raw
    return None


def _resolve_lexical_emotion_label(seg: Dict[str, Any]) -> str | None:
    """Resolve contagious lexical label; zero-hit / empty dicts are ineligible."""
    state = seg.get("emotion_evaluation_state")
    if state in {"failed", "skipped", "empty"}:
        return None
    nrc_data = seg.get("nrc_emotion")
    if not isinstance(nrc_data, dict) or not nrc_data:
        return None
    return _top_positive_label(nrc_data)


def build_emotion_timeline(
    segments: List[Dict[str, Any]], emotion_type: str
) -> Tuple[Dict[str, List[str]], List[Tuple[str, str]]]:
    """Build emotion timeline and speaker emotion sequences."""
    from transcriptx.core.utils.speaker_extraction import (
        extract_speaker_info,
        get_speaker_display_name,
    )
    from transcriptx.utils.text_utils import is_turn_taking_speaker_label

    speaker_emotions = defaultdict(list)
    timeline: List[Tuple[str, str]] = []

    for seg in segments:
        speaker_info = extract_speaker_info(seg)
        if speaker_info is None:
            continue
        speaker = get_speaker_display_name(speaker_info.grouping_key, [seg], segments)
        if not speaker or not is_turn_taking_speaker_label(speaker):
            continue

        if emotion_type == "context_emotion":
            emotion = _resolve_context_emotion_label(seg)
            if emotion is None:
                continue
        else:
            emotion = _resolve_lexical_emotion_label(seg)
            if emotion is None:
                continue

        speaker_emotions[speaker].append(emotion)
        timeline.append((speaker, emotion))

    return dict(speaker_emotions), timeline


def contagion_counts_to_records(
    counts: Dict[Tuple[str, str, str], int] | List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normalize contagion counts to deterministic JSON-safe records."""
    if isinstance(counts, list):
        records = [dict(item) for item in counts if isinstance(item, dict)]
    else:
        records = [
            {
                "actor": str(actor),
                "target": str(target),
                "emotion": str(emotion),
                "count": int(count),
            }
            for (actor, target, emotion), count in counts.items()
        ]
    records.sort(key=lambda r: (r["actor"], r["target"], r["emotion"]))
    return records


def detect_contagion(
    timeline: List[Tuple[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, int]]]:
    """Detect contagion events based on timeline.

    Returns:
        events, contagion_counts (JSON-safe list of {actor,target,emotion,count}),
        and a string-keyed summary map.
    """
    contagion_events: List[Dict[str, Any]] = []
    raw_counts: Dict[Tuple[str, str, str], int] = defaultdict(int)

    for i in range(1, len(timeline)):
        prev_speaker, prev_emotion = timeline[i - 1]
        curr_speaker, curr_emotion = timeline[i]
        if curr_speaker != prev_speaker and curr_emotion == prev_emotion:
            contagion_events.append(
                {
                    "from": prev_speaker,
                    "to": curr_speaker,
                    "emotion": curr_emotion,
                    "turn": i,
                }
            )
            raw_counts[(prev_speaker, curr_speaker, curr_emotion)] += 1

    contagion_counts = contagion_counts_to_records(dict(raw_counts))

    contagion_summary: Dict[str, Dict[str, int]] = {}
    for record in contagion_counts:
        key = f"{record['actor']}->{record['target']}"
        contagion_summary.setdefault(key, {})
        contagion_summary[key][record["emotion"]] = int(record["count"])

    return contagion_events, contagion_counts, contagion_summary
