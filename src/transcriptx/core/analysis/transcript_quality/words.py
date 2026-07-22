"""Flatten transcript words into typed records for ASR confidence analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.transcript_quality.scores import (
    empty_score_normalisation,
    normalize_word_dict,
)


@dataclass(frozen=True)
class WordRecord:
    """One word in deterministic stream order."""

    stream_index: int
    segment_index: int
    word_index: int
    text: str
    speaker: Optional[str]
    start: Optional[float]
    end: Optional[float]
    score: Optional[float]
    eligible: bool
    missing_score: bool
    invalid_score: bool
    out_of_range_score: bool
    unusable: bool


def _coerce_time(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return out


def _word_text(word: Dict[str, Any]) -> str:
    for key in ("word", "text"):
        raw = word.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _segment_speaker(segment: Dict[str, Any]) -> Optional[str]:
    spk = segment.get("speaker")
    if isinstance(spk, str) and spk.strip():
        return spk.strip()
    return None


def extract_word_records(
    segments: List[Dict[str, Any]],
) -> Tuple[List[WordRecord], Dict[str, Any]]:
    """
    Extract ordered word records and aggregate score-normalisation diagnostics.

    Applies the same accept/omit score policy used at ingest so already
    imported transcripts are analysed consistently. Classification uses the raw
    score field before omission so invalid/out-of-range counters stay accurate.
    """
    records: List[WordRecord] = []
    normalisation = empty_score_normalisation()

    for segment_index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue
        words_raw = segment.get("words")
        if not isinstance(words_raw, list):
            continue
        seg_speaker = _segment_speaker(segment)
        for word_index, word in enumerate(words_raw):
            if not isinstance(word, dict):
                continue
            cleaned, verdict = normalize_word_dict(word)
            if verdict.raw_present:
                normalisation["raw_score_present_count"] += 1
            if verdict.accepted is not None:
                normalisation["accepted_score_count"] += 1
            if verdict.invalid:
                normalisation["invalid_score_count"] += 1
            if verdict.out_of_range:
                normalisation["out_of_range_score_count"] += 1

            text = _word_text(cleaned)
            start = _coerce_time(cleaned.get("start"))
            end = _coerce_time(cleaned.get("end"))
            speaker_raw = cleaned.get("speaker")
            speaker = (
                speaker_raw.strip()
                if isinstance(speaker_raw, str) and speaker_raw.strip()
                else seg_speaker
            )
            timing_ok = start is not None and end is not None and end >= start
            unusable = (not text) or (not timing_ok)
            eligible = not unusable
            records.append(
                WordRecord(
                    stream_index=0,  # reassigned after sort
                    segment_index=segment_index,
                    word_index=word_index,
                    text=text,
                    speaker=speaker,
                    start=start,
                    end=end,
                    score=verdict.accepted,
                    eligible=eligible,
                    missing_score=eligible and not verdict.raw_present,
                    invalid_score=eligible and verdict.invalid,
                    out_of_range_score=eligible and verdict.out_of_range,
                    unusable=unusable,
                )
            )

    records.sort(
        key=lambda w: (
            float("inf") if w.start is None else w.start,
            float("inf") if w.end is None else w.end,
            w.segment_index,
            w.word_index,
        )
    )
    records = [
        WordRecord(
            stream_index=i,
            segment_index=r.segment_index,
            word_index=r.word_index,
            text=r.text,
            speaker=r.speaker,
            start=r.start,
            end=r.end,
            score=r.score,
            eligible=r.eligible,
            missing_score=r.missing_score,
            invalid_score=r.invalid_score,
            out_of_range_score=r.out_of_range_score,
            unusable=r.unusable,
        )
        for i, r in enumerate(records)
    ]
    return records, normalisation
