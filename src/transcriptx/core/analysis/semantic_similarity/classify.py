"""Threshold and classify repetition pairs."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .intake import SegmentRow


def classify_pairs(
    rows: List[SegmentRow],
    pairs: List[Tuple[int, int]],
    scores: List[float],
    *,
    self_threshold: float,
    cross_threshold: float,
) -> Dict[str, Any]:
    speaker_repetitions: dict[str, list[dict[str, Any]]] = {}
    cross_speaker: list[dict[str, Any]] = []

    for (i, j), sim in zip(pairs, scores):
        ri, rj = rows[i], rows[j]
        same = ri.speaker_key == rj.speaker_key
        thr = self_threshold if same else cross_threshold
        if sim < thr:
            continue
        entry = {
            "segment1": {
                "id": ri.segment_id,
                "speaker": ri.display_name,
                "text": ri.text,
            },
            "segment2": {
                "id": rj.segment_id,
                "speaker": rj.display_name,
                "text": rj.text,
            },
            "similarity": sim,
            "type": "self" if same else "cross",
        }
        if same:
            speaker_repetitions.setdefault(ri.display_name, []).append(entry)
        else:
            entry["agreement_type"] = "paraphrase"
            cross_speaker.append(entry)

    return {
        "speaker_repetitions": speaker_repetitions,
        "cross_speaker_repetitions": cross_speaker,
    }
