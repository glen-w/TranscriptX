"""
Repetition detection logic for semantic similarity analysis.
"""

from __future__ import annotations

from typing import Any, Callable

from transcriptx.core.utils.logger import log_error, log_warning
from transcriptx.core.utils.nlp_utils import has_meaningful_content
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)
from transcriptx.utils.text_utils import is_named_speaker


def classify_agreement_disagreement_advanced(
    text1: str, text2: str, similarity: float, log_tag: str
) -> str:
    """Simple keyword-based classification for advanced analyzer."""
    try:
        agreement_words = [
            "agree",
            "yes",
            "correct",
            "right",
            "exactly",
            "absolutely",
            "indeed",
        ]
        disagreement_words = [
            "disagree",
            "no",
            "wrong",
            "incorrect",
            "not",
            "never",
            "dispute",
        ]

        text1_lower = text1.lower()
        text2_lower = text2.lower()

        agreement_count = sum(
            1 for word in agreement_words if word in text1_lower or word in text2_lower
        )
        disagreement_count = sum(
            1
            for word in disagreement_words
            if word in text1_lower or word in text2_lower
        )

        if agreement_count > disagreement_count:
            return "agreement"
        if disagreement_count > agreement_count:
            return "disagreement"
        return "neutral"
    except Exception as exc:
        log_warning(log_tag, f"Agreement/disagreement classification failed: {exc}")
        return "neutral"


def classify_agreement_disagreement_basic(text1: str, text2: str, similarity: float) -> str:
    """Classification used by basic analyzer."""
    agreement_words = {
        "agree",
        "yes",
        "exactly",
        "right",
        "correct",
        "absolutely",
        "definitely",
        "sure",
        "certainly",
        "indeed",
        "precisely",
        "that's right",
        "you're right",
        "i agree",
        "i concur",
        "i think so",
        "that makes sense",
        "good point",
    }
    disagreement_words = {
        "disagree",
        "no",
        "wrong",
        "incorrect",
        "not really",
        "i don't think",
        "i disagree",
        "that's not right",
        "that's wrong",
        "i don't agree",
        "but",
        "however",
        "on the other hand",
        "actually",
        "well",
        "i think",
        "i would say",
        "i'm not sure",
        "i don't know",
    }

    text1_lower = text1.lower()
    text2_lower = text2.lower()

    agreement_count = sum(
        1 for word in agreement_words if word in text1_lower or word in text2_lower
    )
    disagreement_count = sum(
        1 for word in disagreement_words if word in text1_lower or word in text2_lower
    )

    if agreement_count > disagreement_count:
        return "agreement"
    if disagreement_count > agreement_count:
        return "disagreement"
    if similarity > 0.8:
        return "paraphrase"
    return "neutral"


def detect_speaker_repetitions_advanced(
    speaker: str,
    segments: list[dict[str, Any]],
    similarity_fn: Callable[[str, str], float],
    comparison_state: Any,
    log_tag: str,
) -> list[dict[str, Any]]:
    """Detect repetitions within a single speaker's segments (advanced)."""
    try:
        repetitions: list[dict[str, Any]] = []

        for i, seg1 in enumerate(segments):
            if comparison_state.comparison_count > comparison_state.max_comparisons:
                break

            text1 = seg1.get("text", "").strip()
            if not has_meaningful_content(text1):
                continue

            for j, seg2 in enumerate(segments[i + 1 :], i + 1):
                if comparison_state.comparison_count > comparison_state.max_comparisons:
                    break

                text2 = seg2.get("text", "").strip()
                if not has_meaningful_content(text2):
                    continue

                time_diff = abs(seg1.get("start", 0) - seg2.get("start", 0))
                if time_diff < 30:
                    continue

                similarity = similarity_fn(text1, text2)
                if similarity > 0.7:
                    repetitions.append(
                        {
                            "type": "self_repetition",
                            "speaker": speaker,
                            "segment1": {
                                "text": seg1["text"],
                                "start": seg1.get("start", 0),
                                "end": seg1.get("end", 0),
                            },
                            "segment2": {
                                "text": seg2["text"],
                                "start": seg2.get("start", 0),
                                "end": seg2.get("end", 0),
                            },
                            "similarity": similarity,
                            "time_gap": time_diff,
                        }
                    )

        return repetitions
    except Exception as exc:
        log_error(
            log_tag,
            f"Speaker repetition detection failed for {speaker}: {exc}",
            exception=exc,
        )
        return []


def detect_cross_speaker_repetitions_advanced(
    segments: list[dict[str, Any]],
    similarity_fn: Callable[[str, str], float],
    comparison_state: Any,
    log_tag: str,
) -> list[dict[str, Any]]:
    """Detect cross-speaker repetitions (advanced)."""
    try:
        repetitions: list[dict[str, Any]] = []

        for i, seg1 in enumerate(segments):
            if comparison_state.comparison_count > comparison_state.max_comparisons:
                break

            speaker1_info = extract_speaker_info(seg1)
            if speaker1_info is None:
                continue
            speaker1 = get_speaker_display_name(
                speaker1_info.grouping_key, [seg1], segments
            )
            if not speaker1 or not is_named_speaker(speaker1):
                continue

            text1 = seg1.get("text", "").strip()
            if not has_meaningful_content(text1):
                continue

            for j, seg2 in enumerate(segments[i + 1 :], i + 1):
                if comparison_state.comparison_count > comparison_state.max_comparisons:
                    break

                speaker2_info = extract_speaker_info(seg2)
                if speaker2_info is None:
                    continue
                speaker2 = get_speaker_display_name(
                    speaker2_info.grouping_key, [seg2], segments
                )
                if not speaker2 or not is_named_speaker(speaker2):
                    continue

                if speaker1_info.grouping_key == speaker2_info.grouping_key:
                    continue

                text2 = seg2.get("text", "").strip()
                if not has_meaningful_content(text2):
                    continue

                time_diff = abs(seg1.get("start", 0) - seg2.get("start", 0))
                if time_diff < 10:
                    continue

                similarity = similarity_fn(text1, text2)
                if similarity > 0.6:
                    classification = classify_agreement_disagreement_advanced(
                        seg1["text"], seg2["text"], similarity, log_tag
                    )
                    repetitions.append(
                        {
                            "type": "cross_speaker_repetition",
                            "speaker1": seg1.get("speaker", ""),
                            "speaker2": seg2.get("speaker", ""),
                            "segment1": {
                                "text": seg1["text"],
                                "start": seg1.get("start", 0),
                                "end": seg1.get("end", 0),
                            },
                            "segment2": {
                                "text": seg2["text"],
                                "start": seg2.get("start", 0),
                                "end": seg2.get("end", 0),
                            },
                            "similarity": similarity,
                            "classification": classification,
                            "time_gap": time_diff,
                        }
                    )

        return repetitions
    except Exception as exc:
        log_error(
            log_tag,
            f"Cross-speaker repetition detection failed: {exc}",
            exception=exc,
        )
        return []


def detect_speaker_repetitions_basic(
    speaker: str,
    segments: list[dict[str, Any]],
    similarity_fn: Callable[[str, str], float],
    comparison_state: Any,
    similarity_threshold: float,
    time_window: int,
    max_segments_per_speaker: int,
    filter_segments_fn: Callable[[list[dict[str, Any]], int], list[dict[str, Any]]],
    log_tag: str,
) -> list[dict[str, Any]]:
    """Detect repetitions within a single speaker's utterances (basic)."""
    repetitions: list[dict[str, Any]] = []
    if len(segments) > max_segments_per_speaker:
        log_warning(
            log_tag,
            f"Limiting {speaker} segments from {len(segments)} to {max_segments_per_speaker} (quality-filtered)",
        )
        segments = filter_segments_fn(segments, max_segments_per_speaker)

    for i, seg1 in enumerate(segments):
        if comparison_state.comparison_count > comparison_state.max_comparisons:
            break

        text1 = seg1.get("text", "").strip()
        if not has_meaningful_content(text1):
            continue

        start_time1 = seg1.get("start", 0)
        max_comparisons_per_segment = 50
        comparisons_made = 0

        for j, seg2 in enumerate(segments[i + 1 :], i + 1):
            if comparisons_made >= max_comparisons_per_segment:
                break

            text2 = seg2.get("text", "").strip()
            if not has_meaningful_content(text2):
                continue

            start_time2 = seg2.get("start", 0)
            time_diff = start_time2 - start_time1
            if time_diff > time_window:
                continue

            similarity = similarity_fn(text1, text2)
            comparisons_made += 1

            if similarity >= similarity_threshold:
                repetitions.append(
                    {
                        "speaker": speaker,
                        "segment1": {
                            "index": i,
                            "text": text1,
                            "start": start_time1,
                            "end": seg1.get("end", start_time1),
                        },
                        "segment2": {
                            "index": j,
                            "text": text2,
                            "start": start_time2,
                            "end": seg2.get("end", start_time2),
                        },
                        "similarity": similarity,
                        "time_gap": time_diff,
                        "type": "self_repetition",
                    }
                )

    return repetitions


def detect_cross_speaker_repetitions_basic(
    segments: list[dict[str, Any]],
    similarity_fn: Callable[[str, str], float],
    comparison_state: Any,
    similarity_threshold: float,
    time_window: int,
    max_segments_for_cross_speaker: int,
    log_tag: str,
) -> list[dict[str, Any]]:
    """Detect cross-speaker repetitions (basic)."""
    cross_repetitions: list[dict[str, Any]] = []

    max_segments_for_cross = min(len(segments), max_segments_for_cross_speaker)
    if len(segments) > max_segments_for_cross:
        log_warning(
            log_tag,
            f"Limiting cross-speaker analysis from {len(segments)} to {max_segments_for_cross} segments",
        )
        segments = segments[:max_segments_for_cross]

    for i, seg1 in enumerate(segments):
        if comparison_state.comparison_count > comparison_state.max_comparisons:
            log_warning(
                log_tag,
                "Stopping cross-speaker analysis due to comparison limit",
            )
            break

        speaker1_info = extract_speaker_info(seg1)
        if speaker1_info is None:
            continue
        speaker1 = get_speaker_display_name(
            speaker1_info.grouping_key, [seg1], segments
        )
        if not speaker1 or not is_named_speaker(speaker1):
            continue

        text1 = seg1.get("text", "").strip()
        if not text1 or len(text1.split()) < 3:
            continue

        start_time1 = seg1.get("start", 0)
        max_cross_comparisons_per_segment = 30
        comparisons_made = 0

        for j, seg2 in enumerate(segments[i + 1 :], i + 1):
            if comparisons_made >= max_cross_comparisons_per_segment:
                break

            speaker2_info = extract_speaker_info(seg2)
            if speaker2_info is None:
                continue
            speaker2 = get_speaker_display_name(
                speaker2_info.grouping_key, [seg2], segments
            )
            if not speaker2 or not is_named_speaker(speaker2):
                continue

            if speaker1_info.grouping_key == speaker2_info.grouping_key:
                continue

            text2 = seg2.get("text", "").strip()
            if not text2 or len(text2.split()) < 3:
                continue

            start_time2 = seg2.get("start", 0)
            time_diff = start_time2 - start_time1
            if time_diff > time_window:
                continue

            similarity = similarity_fn(text1, text2)
            comparisons_made += 1

            if similarity >= similarity_threshold:
                agreement_type = classify_agreement_disagreement_basic(
                    text1, text2, similarity
                )
                cross_repetitions.append(
                    {
                        "speaker1": speaker1,
                        "speaker2": speaker2,
                        "segment1": {
                            "index": i,
                            "text": text1,
                            "start": start_time1,
                            "end": seg1.get("end", start_time1),
                        },
                        "segment2": {
                            "index": j,
                            "text": text2,
                            "start": start_time2,
                            "end": seg2.get("end", start_time2),
                        },
                        "similarity": similarity,
                        "time_gap": time_diff,
                        "type": "cross_speaker",
                        "agreement_type": agreement_type,
                    }
                )

    return cross_repetitions
