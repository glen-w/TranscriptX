"""
Emotion data reconstruction utilities for contagion analysis.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)


def reconstruct_emotion_data(
    segments: List[Dict[str, Any]],
    emotion_data: Dict[str, Any],
    logger: Any,
) -> Tuple[List[Dict[str, Any]], str, bool]:
    """
    Reconstruct emotion data from emotion_data when segments_with_emotion lacks emotion fields.
    """
    contextual_examples = emotion_data.get("contextual_examples", {})
    contextual_all = emotion_data.get("contextual_all", {})
    nrc_scores = emotion_data.get("nrc_scores", {})

    logger.debug(
        "[CONTAGION] Reconstruction attempt - contextual_all: "
        f"{len(contextual_all) if contextual_all else 0} speakers, "
        f"contextual_examples: {len(contextual_examples) if contextual_examples else 0} speakers, "
        f"nrc_scores: {len(nrc_scores) if nrc_scores else 0} speakers"
    )

    if contextual_all:
        logger.debug("[CONTAGION] Reconstructing emotion data from contextual_all...")
        speaker_emotion_lists = {}
        for speaker, emotion_list in contextual_all.items():
            if emotion_list and isinstance(emotion_list, list) and len(emotion_list) > 0:
                speaker_emotion_lists[speaker] = emotion_list

        if speaker_emotion_lists:
            merged_count = 0
            speaker_segment_indices = defaultdict(int)

            for seg in segments:
                speaker_info = extract_speaker_info(seg)
                if speaker_info is None:
                    continue
                speaker = get_speaker_display_name(
                    speaker_info.grouping_key, [seg], segments
                )
                if not speaker or speaker not in speaker_emotion_lists:
                    continue

                text = seg.get("text", "").strip()
                if not text:
                    continue

                emotion_list = speaker_emotion_lists[speaker]
                idx = speaker_segment_indices[speaker]
                if idx < len(emotion_list):
                    emotion = emotion_list[idx]
                    if emotion:
                        seg["context_emotion"] = emotion
                        merged_count += 1
                    speaker_segment_indices[speaker] += 1

            if merged_count > 0:
                logger.debug(
                    "[CONTAGION] Reconstructed context_emotion for "
                    f"{merged_count}/{len(segments)} segments from contextual_all"
                )
                return segments, "context_emotion", True
            logger.debug(
                "[CONTAGION] contextual_all available but no matches found. "
                f"Speaker emotion counts: {[(s, len(l)) for s, l in speaker_emotion_lists.items()]}"
            )

    if contextual_examples:
        logger.debug(
            "[CONTAGION] Reconstructing emotion data from contextual_examples..."
        )
        text_to_emotion = {}
        for speaker, emotion_dict in contextual_examples.items():
            for emotion, examples in emotion_dict.items():
                for score, text in examples:
                    normalized_text = text.strip().lower()
                    if normalized_text:
                        if (speaker, normalized_text) not in text_to_emotion:
                            text_to_emotion[(speaker, normalized_text)] = (emotion, score)
                        else:
                            existing_score = text_to_emotion[(speaker, normalized_text)][1]
                            if score > existing_score:
                                text_to_emotion[(speaker, normalized_text)] = (
                                    emotion,
                                    score,
                                )

        merged_count = 0
        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )
            if not speaker:
                continue

            text = seg.get("text", "").strip().lower()
            if text and (speaker, text) in text_to_emotion:
                emotion, score = text_to_emotion[(speaker, text)]
                seg["context_emotion"] = emotion
                merged_count += 1

        if merged_count > 0:
            logger.debug(
                "[CONTAGION] Reconstructed context_emotion for "
                f"{merged_count}/{len(segments)} segments from contextual_examples"
            )
            return segments, "context_emotion", True

    if nrc_scores:
        logger.debug(
            "[CONTAGION] Using aggregated nrc_scores per speaker as fallback..."
        )
        merged_count = 0
        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )
            if not speaker or speaker not in nrc_scores:
                continue

            speaker_nrc = nrc_scores[speaker]
            if speaker_nrc and any(v > 0 for v in speaker_nrc.values()):
                seg["nrc_emotion"] = speaker_nrc.copy()
                merged_count += 1

        if merged_count > 0:
            logger.debug(
                "[CONTAGION] Added nrc_emotion for "
                f"{merged_count}/{len(segments)} segments from aggregated scores"
            )
            return segments, "nrc_emotion", True

    logger.warning(
        "[CONTAGION] Failed to reconstruct emotion data. Available data: "
        f"contextual_all={bool(contextual_all)}, "
        f"contextual_examples={bool(contextual_examples)}, "
        f"nrc_scores={bool(nrc_scores)}"
    )
    return segments, None, False
