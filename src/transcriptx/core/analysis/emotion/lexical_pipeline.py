"""Frozen NRC lexical pipeline v1: occurrence coverage, valence split, offsets."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

NRC_LEXICAL_PIPELINE_V1 = "nrc_lexical_pipeline_v1"
SCHEMA_VERSION = "transcriptx.emotion_result.v1"
SEMANTICS_VERSION = "emotion_lexical_v2"

PLUTCHIK_EIGHT = (
    "anger",
    "anticipation",
    "disgust",
    "fear",
    "joy",
    "sadness",
    "surprise",
    "trust",
)
VALENCE_KEYS = ("positive", "negative")

# Word-like tokens with original offsets (Unicode letter/number sequences)
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class MatchedOccurrence:
    original_start: int
    original_end: int
    surface: str
    normalized_token: str
    categories: list[str] = field(default_factory=list)


@dataclass
class LexicalSegmentResult:
    evaluation_state: str
    tokens_considered: int
    matched_occurrences: int
    coverage: float
    assignment_counts: dict[str, int]
    valence_assignment_counts: dict[str, int]
    emotion_scores: dict[str, float]
    valence_scores: dict[str, float]
    contributing: list[dict[str, Any]]
    language_resolution: str
    warnings: list[str] = field(default_factory=list)


def _lookup_key(surface: str) -> str:
    return unicodedata.normalize("NFC", surface).casefold()


def _zero_scores(keys: tuple[str, ...]) -> dict[str, float]:
    return {k: 0.0 for k in keys}


def normalize_profile(
    counts: dict[str, int], keys: tuple[str, ...]
) -> dict[str, float]:
    total = sum(int(counts.get(k, 0)) for k in keys)
    if total <= 0:
        return _zero_scores(keys)
    return {k: float(counts.get(k, 0)) / float(total) for k in keys}


# Back-compat alias
_normalize_profile = normalize_profile


def build_lexicon_from_nrclex(nrclex_cls: Any) -> dict[str, list[str]]:
    """Build token → categories map from NRCLex ``lexicon`` / AffectDict."""
    lexicon: dict[str, list[str]] = {}
    try:
        if hasattr(nrclex_cls, "load_raw_text"):
            probe = nrclex_cls()
            probe.load_raw_text("x")
        else:
            probe = nrclex_cls("x")
    except TypeError:
        probe = nrclex_cls("x")

    # nrclex 4.x stores the map on ``__lexicon__``; older releases used
    # ``lexicon`` / ``AffectDict`` / ``affect_dict``.
    source = (
        getattr(probe, "lexicon", None)
        or getattr(probe, "__lexicon__", None)
        or getattr(probe, "AffectDict", None)
        or getattr(nrclex_cls, "AffectDict", None)
        or getattr(probe, "affect_dict", None)
    )
    if not isinstance(source, dict) or not source:
        return lexicon

    for word, cats in source.items():
        key = _lookup_key(str(word))
        if not key:
            continue
        cat_list = [str(c).casefold() for c in (cats or [])]
        cat_list = ["anticipation" if c == "anticip" else c for c in cat_list]
        lexicon[key] = cat_list
    return lexicon


def score_segment_text(
    text: str,
    lexicon: dict[str, list[str]],
    *,
    language_resolution: str = "assumed_en_missing_metadata",
) -> LexicalSegmentResult:
    original = text if text is not None else ""
    if not original.strip():
        return LexicalSegmentResult(
            evaluation_state="empty",
            tokens_considered=0,
            matched_occurrences=0,
            coverage=0.0,
            assignment_counts={k: 0 for k in PLUTCHIK_EIGHT},
            valence_assignment_counts={k: 0 for k in VALENCE_KEYS},
            emotion_scores=_zero_scores(PLUTCHIK_EIGHT),
            valence_scores=_zero_scores(VALENCE_KEYS),
            contributing=[],
            language_resolution=language_resolution,
        )

    assignment = {k: 0 for k in PLUTCHIK_EIGHT}
    valence_assignment = {k: 0 for k in VALENCE_KEYS}
    contributing: list[dict[str, Any]] = []
    tokens_considered = 0
    matched_occurrences = 0

    for match in _TOKEN_RE.finditer(original):
        tokens_considered += 1
        start, end = match.start(), match.end()
        surface = original[start:end]
        key = _lookup_key(surface)
        cats = lexicon.get(key) or []
        if not cats:
            continue
        matched_occurrences += 1
        emotion_cats = []
        for c in cats:
            if c in assignment:
                assignment[c] += 1
                emotion_cats.append(c)
            elif c in valence_assignment:
                valence_assignment[c] += 1
                emotion_cats.append(c)
        contributing.append(
            {
                "original_start": start,
                "original_end": end,
                "surface": surface,
                "normalized_token": key,
                "categories": emotion_cats,
            }
        )

    coverage = (
        float(matched_occurrences) / float(tokens_considered)
        if tokens_considered > 0
        else 0.0
    )
    return LexicalSegmentResult(
        evaluation_state="scored",
        tokens_considered=tokens_considered,
        matched_occurrences=matched_occurrences,
        coverage=coverage,
        assignment_counts=assignment,
        valence_assignment_counts=valence_assignment,
        emotion_scores=_normalize_profile(assignment, PLUTCHIK_EIGHT),
        valence_scores=_normalize_profile(valence_assignment, VALENCE_KEYS),
        contributing=contributing,
        language_resolution=language_resolution,
    )


def sum_assignment_maps(
    maps: list[dict[str, int]], keys: tuple[str, ...]
) -> dict[str, int]:
    out = {k: 0 for k in keys}
    for m in maps:
        for k in keys:
            out[k] += int(m.get(k, 0))
    return out
