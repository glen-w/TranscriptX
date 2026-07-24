"""Topic-shift-specific segment canonicalisation (independent of insight_eligibility)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from transcriptx.core.analysis.topic_shift.semantics import DEFAULT_MIN_TEXT_CHARS

# Fixed stoplist for lexical channel / keyword hints (deterministic, no NLP runtime).
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "as",
        "by",
        "with",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "not",
        "no",
        "yes",
        "so",
        "than",
        "too",
        "very",
        "just",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "out",
        "up",
        "down",
        "off",
        "again",
        "further",
        "then",
        "once",
        "also",
        "um",
        "uh",
        "ah",
        "er",
        "hmm",
        "like",
        "okay",
        "ok",
        "yeah",
        "yep",
        "right",
    }
)

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CanonicalTopicSegment:
    """One analysable segment with original source identity retained."""

    source_index: int
    canonical_position: int
    start: float
    end: float
    raw_text: str
    lexical_text: str


@dataclass(frozen=True)
class SegmentCanonicalisationResult:
    segments: tuple[CanonicalTopicSegment, ...]
    skipped_invalid: int
    skipped_empty: int
    analytical_status: Optional[str]
    """Set when canonicalisation itself fails the run (invalid_input / insufficient)."""


def light_normalize_raw(text: str) -> str:
    """Sentence-like text for transformer embeddings."""
    cleaned = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def lexical_tokens(text: str) -> list[str]:
    """Deterministic regex tokens minus fixed stoplist (lowercase)."""
    tokens: list[str] = []
    for match in _WORD_RE.finditer(str(text or "")):
        tok = match.group(0).lower()
        if tok in _STOPWORDS:
            continue
        if len(tok) < 2:
            continue
        tokens.append(tok)
    return tokens


def lexical_text_from_raw(raw: str) -> str:
    return " ".join(lexical_tokens(raw))


def _valid_timestamps(start: Any, end: Any) -> tuple[float, float] | None:
    try:
        s = float(start)
        e = float(end)
    except (TypeError, ValueError):
        return None
    if s != s or e != e:  # NaN
        return None
    if e < s:
        return None
    return s, e


def canonicalise_segments(
    segments: Sequence[MappingLike],
    *,
    min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
    max_skip_ratio: float = 0.5,
    max_absolute_skips: int = 200,
) -> SegmentCanonicalisationResult:
    """
    Validate, sort by time, retain source_index.

    Invalid timestamps are explicitly skipped (not silently reindexed).
    Overlaps are allowed; order is by (start, end, source_index).
    """
    raw_list = list(segments or [])
    n = len(raw_list)
    if n == 0:
        return SegmentCanonicalisationResult(
            segments=(),
            skipped_invalid=0,
            skipped_empty=0,
            analytical_status="insufficient_content",
        )

    pending: list[tuple[int, float, float, str]] = []
    skipped_invalid = 0
    skipped_empty = 0

    for source_index, seg in enumerate(raw_list):
        if not isinstance(seg, dict):
            skipped_invalid += 1
            continue
        times = _valid_timestamps(seg.get("start"), seg.get("end"))
        if times is None:
            skipped_invalid += 1
            continue
        start, end = times
        raw = light_normalize_raw(str(seg.get("text", "")))
        if len(raw) < min_text_chars:
            skipped_empty += 1
            continue
        pending.append((source_index, start, end, raw))

    total_skipped = skipped_invalid + skipped_empty
    if n > 0 and total_skipped >= n:
        status = (
            "invalid_input"
            if skipped_invalid >= skipped_empty
            else "insufficient_content"
        )
        return SegmentCanonicalisationResult(
            segments=(),
            skipped_invalid=skipped_invalid,
            skipped_empty=skipped_empty,
            analytical_status=status,
        )
    if total_skipped > max_absolute_skips or (
        n > 0 and total_skipped / n > max_skip_ratio and len(pending) < 2
    ):
        return SegmentCanonicalisationResult(
            segments=(),
            skipped_invalid=skipped_invalid,
            skipped_empty=skipped_empty,
            analytical_status="invalid_input",
        )

    pending.sort(key=lambda row: (row[1], row[2], row[0]))
    out: list[CanonicalTopicSegment] = []
    for pos, (source_index, start, end, raw) in enumerate(pending):
        out.append(
            CanonicalTopicSegment(
                source_index=source_index,
                canonical_position=pos,
                start=start,
                end=end,
                raw_text=raw,
                lexical_text=lexical_text_from_raw(raw),
            )
        )

    if len(out) < 2:
        return SegmentCanonicalisationResult(
            segments=tuple(out),
            skipped_invalid=skipped_invalid,
            skipped_empty=skipped_empty,
            analytical_status="insufficient_content",
        )

    return SegmentCanonicalisationResult(
        segments=tuple(out),
        skipped_invalid=skipped_invalid,
        skipped_empty=skipped_empty,
        analytical_status=None,
    )


# Typing alias without importing Mapping from typing for dict duck-typing
MappingLike = Any
