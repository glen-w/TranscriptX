"""Content filtering for shared insight eligibility."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from transcriptx.core.utils.nlp_runtime import get_nlp_model
from transcriptx.core.utils.nlp_utils import (
    ALL_DISCOURSE_STOPWORDS,
    ALL_VERBAL_TICS,
    DISCOURSE_VERBS,
    build_tic_mask,
)


@dataclass(frozen=True)
class FilteredSegment:
    segment_index: int
    speaker: str
    start: float
    end: float
    raw_text: str
    content_tokens: List[str]
    content_text: str
    content_density: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_tic_terms(tics_result: Optional[Dict[str, Any]]) -> Set[str]:
    if not isinstance(tics_result, dict):
        return set()
    extracted: Set[str] = set()

    global_stats = tics_result.get("global_stats") or {}
    if isinstance(global_stats, dict):
        extracted.update(
            str(term).lower() for term in global_stats.keys() if term != "total_tics"
        )

    speaker_stats = tics_result.get("speaker_stats") or {}
    if isinstance(speaker_stats, dict):
        for speaker_terms in speaker_stats.values():
            if isinstance(speaker_terms, dict):
                extracted.update(str(term).lower() for term in speaker_terms.keys())

    tic_counts = tics_result.get("tic_counts") or {}
    if isinstance(tic_counts, dict):
        for counter_like in tic_counts.values():
            if isinstance(counter_like, dict):
                extracted.update(str(term).lower() for term in counter_like.keys())

    return extracted


def _speaker_from_segment(segment: Dict[str, Any]) -> str:
    return str(segment.get("speaker_display") or segment.get("speaker") or "").strip()


def filter_segments_for_insights(
    segments: List[Dict[str, Any]],
    *,
    tics_result: Optional[Dict[str, Any]] = None,
) -> Tuple[List[FilteredSegment], Set[str], Dict[str, List[str]]]:
    """Filter segments to content-bearing terms and compute segment density."""
    nlp = get_nlp_model()
    allowed_tags = {"NOUN", "PROPN", "ADJ", "VERB", "AUX"}
    detected_tics = _extract_tic_terms(tics_result)
    tic_mask = build_tic_mask(detected_tics)
    tic_mask_sources: Dict[str, List[str]] = {
        "from_detected_tics": sorted(detected_tics),
        "from_verbal_tics_stoplist": sorted(
            {str(term).lower() for term in ALL_VERBAL_TICS}
        ),
        "from_discourse_stoplist": sorted(
            {str(term).lower() for term in ALL_DISCOURSE_STOPWORDS}
        ),
    }

    filtered: List[FilteredSegment] = []
    for idx, segment in enumerate(segments):
        text = str(segment.get("text", "") or "").strip()
        if not text:
            continue

        doc = nlp(text.lower())
        content_tokens: List[str] = []
        all_alpha = 0
        for token in doc:
            if not token.is_alpha:
                continue
            all_alpha += 1
            if token.pos_ not in allowed_tags:
                continue
            token_text = token.text.lower()
            token_lemma = token.lemma_.lower()
            if token_text in tic_mask or token_lemma in tic_mask:
                continue
            if token.pos_ in {"VERB", "AUX"} and token_lemma in DISCOURSE_VERBS:
                continue
            content_tokens.append(token_text)

        density = (
            float(len(content_tokens)) / float(all_alpha) if all_alpha > 0 else 0.0
        )
        if not content_tokens:
            continue

        filtered.append(
            FilteredSegment(
                segment_index=int(segment.get("segment_index", idx)),
                speaker=_speaker_from_segment(segment),
                start=float(segment.get("start", 0.0) or 0.0),
                end=float(segment.get("end", 0.0) or 0.0),
                raw_text=text,
                content_tokens=content_tokens,
                content_text=" ".join(content_tokens),
                content_density=density,
            )
        )

    filtered.sort(key=lambda seg: (seg.segment_index, seg.start, seg.end, seg.raw_text))
    return filtered, tic_mask, tic_mask_sources
