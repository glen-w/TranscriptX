"""
Emotion data merging utilities for contagion analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def merge_emotion_data(
    segments: List[Dict[str, Any]],
    segments_with_emotion: List[Dict[str, Any]],
    logger: Any,
    tolerance: float = 0.5,
) -> Tuple[List[Dict[str, Any]], str, bool]:
    """
    Merge emotion data from segments_with_emotion into segments by matching start times.
    """
    if not segments_with_emotion:
        logger.debug("merge_emotion_data: segments_with_emotion is empty")
        return segments, None, False

    emotion_map: Dict[float, List[Dict[str, Any]]] = {}
    for emotion_seg in segments_with_emotion:
        start = emotion_seg.get("start", 0)
        if start not in emotion_map:
            emotion_map[start] = []
        emotion_map[start].append(emotion_seg)

    merged_count = 0
    emotion_type = None

    for seg in segments:
        seg_start = seg.get("start", 0)
        matched = False

        if seg_start in emotion_map:
            for emotion_seg in emotion_map[seg_start]:
                if "context_emotion" in emotion_seg and emotion_seg["context_emotion"]:
                    seg["context_emotion"] = emotion_seg["context_emotion"]
                    emotion_type = "context_emotion"
                    matched = True
                    merged_count += 1
                    break
                if "nrc_emotion" in emotion_seg:
                    nrc_data = emotion_seg.get("nrc_emotion", {})
                    if (
                        isinstance(nrc_data, dict)
                        and nrc_data
                        and any(v > 0 for v in nrc_data.values())
                    ):
                        seg["nrc_emotion"] = nrc_data
                        if not emotion_type:
                            emotion_type = "nrc_emotion"
                        matched = True
                        merged_count += 1
                        break
            if matched:
                continue

        if not matched:
            for emotion_start, emotion_segs in emotion_map.items():
                if abs(seg_start - emotion_start) < tolerance:
                    for emotion_seg in emotion_segs:
                        if (
                            "context_emotion" in emotion_seg
                            and emotion_seg["context_emotion"]
                        ):
                            seg["context_emotion"] = emotion_seg["context_emotion"]
                            emotion_type = "context_emotion"
                            matched = True
                            merged_count += 1
                            break
                        if "nrc_emotion" in emotion_seg:
                            nrc_data = emotion_seg.get("nrc_emotion", {})
                            if (
                                isinstance(nrc_data, dict)
                                and nrc_data
                                and any(v > 0 for v in nrc_data.values())
                            ):
                                seg["nrc_emotion"] = nrc_data
                                if not emotion_type:
                                    emotion_type = "nrc_emotion"
                                matched = True
                                merged_count += 1
                                break
                    if matched:
                        break

    found = merged_count > 0
    if found:
        logger.debug(
            "merge_emotion_data: Successfully merged emotion data into "
            f"{merged_count}/{len(segments)} segments, type: {emotion_type}"
        )
    else:
        logger.debug(
            "merge_emotion_data: Failed to merge emotion data. Checked "
            f"{len(segments)} segments against {len(segments_with_emotion)} emotion segments"
        )

    return segments, emotion_type, found
