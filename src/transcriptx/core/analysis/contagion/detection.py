"""
Contagion detection utilities.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple


def _top_score_label(scores: Dict[str, Any]) -> str | None:
    numeric = {k: v for k, v in scores.items() if isinstance(v, (int, float)) and v > 0}
    if not numeric:
        return None
    return max(numeric.items(), key=lambda x: x[1])[0]


def _resolve_context_emotion_label(seg: Dict[str, Any]) -> str:
    raw = seg.get("context_emotion")
    if isinstance(raw, dict) and raw:
        label = _top_score_label(raw)
        return label if label is not None else "neutral"
    if raw:
        return str(raw)
    primary = seg.get("context_emotion_primary")
    if primary:
        return str(primary)
    scores = seg.get("context_emotion_scores")
    if isinstance(scores, dict):
        label = _top_score_label(scores)
        if label is not None:
            return label
    return "neutral"


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
        else:
            nrc_data = seg.get("nrc_emotion", {})
            if nrc_data:
                emotion = (
                    max(nrc_data.items(), key=lambda x: x[1])[0]
                    if nrc_data
                    else "neutral"
                )
            else:
                emotion = "neutral"

        speaker_emotions[speaker].append(emotion)
        timeline.append((speaker, emotion))

    return dict(speaker_emotions), timeline


def detect_contagion(
    timeline: List[Tuple[str, str]],
) -> Tuple[
    List[Dict[str, Any]], Dict[Tuple[str, str, str], int], Dict[str, Dict[str, int]]
]:
    """Detect contagion events based on timeline."""
    contagion_events = []
    contagion_counts = Counter()

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
            contagion_counts[(prev_speaker, curr_speaker, curr_emotion)] += 1

    contagion_summary = defaultdict(lambda: defaultdict(int))
    for (from_spk, to_spk, emo), count in contagion_counts.items():
        contagion_summary[(from_spk, to_spk)][emo] = count

    json_serializable_summary = {}
    for (from_spk, to_spk), emotion_counts in contagion_summary.items():
        key = f"{from_spk}->{to_spk}"
        json_serializable_summary[key] = dict(emotion_counts)

    return contagion_events, dict(contagion_counts), json_serializable_summary
