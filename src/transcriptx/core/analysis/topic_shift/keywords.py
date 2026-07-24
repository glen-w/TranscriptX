"""Deterministic keyword hints per final coverage span."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from transcriptx.core.analysis.topic_shift.segments import (
    CanonicalTopicSegment,
    lexical_tokens,
)

# Extra discourse / filler tokens stripped only for chapter titles/subtitles.
# Keep separate from segments._STOPWORDS so TF-IDF / embedding semantics stay fixed.
_HINT_EXTRA_STOPWORDS = frozenset(
    {
        "it's",
        "i'm",
        "i've",
        "i'll",
        "don't",
        "doesn't",
        "didn't",
        "won't",
        "wouldn't",
        "couldn't",
        "shouldn't",
        "can't",
        "cannot",
        "that's",
        "there's",
        "they're",
        "we're",
        "you're",
        "he's",
        "she's",
        "what's",
        "who's",
        "let's",
        "think",
        "know",
        "mean",
        "means",
        "kind",
        "sort",
        "thing",
        "things",
        "something",
        "anything",
        "everything",
        "nothing",
        "because",
        "really",
        "actually",
        "basically",
        "literally",
        "maybe",
        "probably",
        "perhaps",
        "going",
        "gonna",
        "wanna",
        "gotta",
        "yeah",
        "yep",
        "yup",
        "nah",
        "okay",
        "ok",
        "alright",
        "well",
        "sure",
        "right",
        "quite",
        "rather",
        "pretty",
        "bit",
        "lot",
        "lots",
        "much",
        "many",
        "more",
        "most",
        "some",
        "any",
        "such",
        "even",
        "still",
        "already",
        "always",
        "never",
        "often",
        "sometimes",
        "else",
        "other",
        "another",
        "same",
        "different",
        "good",
        "great",
        "bad",
        "nice",
        "fine",
        "get",
        "got",
        "getting",
        "make",
        "made",
        "making",
        "see",
        "saw",
        "look",
        "looking",
        "say",
        "said",
        "says",
        "saying",
        "tell",
        "told",
        "come",
        "came",
        "coming",
        "want",
        "wanted",
        "needs",
        "needed",
        "try",
        "trying",
        "tried",
        "use",
        "used",
        "using",
        "way",
        "ways",
        "time",
        "times",
        "people",
        "person",
        "stuff",
        "point",
        "points",
        "one",
        "two",
        "three",
        "first",
        "second",
        "next",
        "last",
        "new",
        "old",
        "big",
        "small",
        "little",
        "able",
        "easy",
        "hard",
        "important",
        "interesting",
        "obviously",
        "honestly",
        "anyway",
        "anymore",
        "whatever",
        "whoever",
        "wherever",
        "whenever",
        "however",
        "therefore",
        "though",
        "although",
        "unless",
        "until",
        "while",
        "since",
        "during",
        "around",
        "across",
        "through",
        "without",
        "within",
        "among",
        "against",
        "upon",
        "onto",
        "into",
        "under",
        "above",
        "below",
        "between",
        "both",
        "each",
        "every",
        "few",
        "own",
        "all",
        "whole",
        "part",
        "parts",
        "side",
        "back",
        "front",
        "end",
        "start",
        "started",
        "starting",
        "done",
        "doing",
        "does",
        "did",
        "been",
        "being",
        "am",
        "'m",
        "'re",
        "'ve",
        "'ll",
        "'d",
        "n't",
    }
)


def _hint_tokens(text: str) -> list[str]:
    out: list[str] = []
    for tok in lexical_tokens(text):
        if tok in _HINT_EXTRA_STOPWORDS:
            continue
        # Prefer content-ish tokens; keep short proper-ish tokens (phd, ai, q3).
        if len(tok) < 3 and not tok.isalnum():
            continue
        if len(tok) < 3 and tok.isalpha():
            continue
        # Drop pure numerics (page counts, years can stay if mixed).
        if tok.isdigit():
            continue
        out.append(tok)
    return out


def is_hint_stopword(token: str) -> bool:
    """True when a token should not appear in chapter titles/subtitles."""
    tok = str(token or "").strip().casefold()
    if not tok:
        return True
    if tok in _HINT_EXTRA_STOPWORDS:
        return True
    if tok.isdigit():
        return True
    return False


def keyword_hints_for_segments(
    segs: Sequence[CanonicalTopicSegment],
    *,
    max_hints: int = 6,
) -> list[str]:
    counts: Counter[str] = Counter()
    for seg in segs:
        # Prefer raw_text so named entities survive light stopwording.
        counts.update(_hint_tokens(seg.raw_text or seg.lexical_text))
    # Prefer longer, more frequent tokens; break ties alphabetically.
    ranked = sorted(
        counts.items(),
        key=lambda kv: (-kv[1], -len(kv[0]), kv[0]),
    )
    return [tok for tok, _ in ranked[: max(0, int(max_hints))]]


def hints_for_span_ranges(
    segments: Sequence[CanonicalTopicSegment],
    ranges: Sequence[tuple[int, int]],
    *,
    max_hints: int = 6,
) -> list[list[str]]:
    ordered = list(segments)
    out: list[list[str]] = []
    for c0, c1 in ranges:
        segs = [s for s in ordered if c0 <= s.canonical_position <= c1]
        out.append(keyword_hints_for_segments(segs, max_hints=max_hints))
    return out


def text_excerpt_for_segments(
    segs: Sequence[CanonicalTopicSegment],
    *,
    max_chars: int = 480,
) -> str:
    """Compact span excerpt for LLM enrichment (deterministic truncate)."""
    parts: list[str] = []
    total = 0
    for seg in segs:
        text = (seg.raw_text or "").strip()
        if not text:
            continue
        if total >= max_chars:
            break
        remain = max_chars - total
        chunk = text if len(text) <= remain else text[:remain].rsplit(" ", 1)[0]
        if not chunk:
            break
        parts.append(chunk)
        total += len(chunk) + 1
    return " ".join(parts).strip()
