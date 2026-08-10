"""Word ↔ character span mapping for transcript segment corrections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


class AmbiguousFindError(ValueError):
    """Raised when a find needle matches more than one occurrence in segment text."""

    def __init__(self, needle: str, match_count: int, matches: List[Tuple[int, int]]):
        self.needle = needle
        self.match_count = match_count
        self.matches = matches
        super().__init__(
            f"Ambiguous find for {needle!r}: {match_count} matches; narrow the selection"
        )


class WordSpanAlignmentError(ValueError):
    """Raised when words[] cannot be reliably aligned to segment text."""


@dataclass(frozen=True)
class WordSpan:
    """One token mapped into segment text character coordinates."""

    word_index: int
    text: str
    char_start: int
    char_end: int
    start: Optional[float] = None
    end: Optional[float] = None
    score: Optional[float] = None
    aligned: bool = True


def _word_token_text(word: Dict[str, Any]) -> str:
    for key in ("word", "text"):
        raw = word.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


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


def _whitespace_spans(text: str) -> List[Tuple[int, int, str]]:
    spans: List[Tuple[int, int, str]] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        j = i
        while j < n and not text[j].isspace():
            j += 1
        spans.append((i, j, text[i:j]))
        i = j
    return spans


def align_words_to_text(
    text: str, words: Sequence[Dict[str, Any]]
) -> Tuple[List[WordSpan], bool]:
    """
    Greedy left-to-right alignment of ``words`` into ``text``.

    Returns ``(spans, aligned_ok)``. When alignment fails, falls back to
    whitespace tokenization of ``text`` with ``aligned=False``.
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    if not words:
        return [], True

    spans: List[WordSpan] = []
    cursor = 0
    for wi, raw in enumerate(words):
        if not isinstance(raw, dict):
            return _fallback_whitespace_spans(text), False
        token = _word_token_text(raw)
        if not token:
            continue
        idx = text.find(token, cursor)
        if idx < 0:
            # Try casefold match for ASR casing drift
            lower_text = text.casefold()
            lower_tok = token.casefold()
            idx = lower_text.find(lower_tok, cursor)
            if idx < 0:
                return _fallback_whitespace_spans(text), False
            end = idx + len(token)
            # Prefer exact slice length from original text
            matched = text[idx:end]
            if matched.casefold() != lower_tok:
                return _fallback_whitespace_spans(text), False
        else:
            end = idx + len(token)
        spans.append(
            WordSpan(
                word_index=wi,
                text=text[idx:end],
                char_start=idx,
                char_end=end,
                start=_coerce_time(raw.get("start")),
                end=_coerce_time(raw.get("end")),
                score=raw.get("score") if isinstance(raw.get("score"), (int, float)) else None,
                aligned=True,
            )
        )
        cursor = end
    return spans, True


def _fallback_whitespace_spans(text: str) -> List[WordSpan]:
    out: List[WordSpan] = []
    for i, (start, end, tok) in enumerate(_whitespace_spans(text)):
        out.append(
            WordSpan(
                word_index=i,
                text=tok,
                char_start=start,
                char_end=end,
                aligned=False,
            )
        )
    return out


def iter_segment_word_spans(segment: Dict[str, Any]) -> Tuple[List[WordSpan], bool]:
    """Return word spans for a segment and whether ``words[]`` aligned to text."""
    text = segment.get("text") or ""
    if not isinstance(text, str):
        text = str(text)
    words_raw = segment.get("words")
    if isinstance(words_raw, list) and words_raw:
        return align_words_to_text(text, words_raw)
    return _fallback_whitespace_spans(text), False


def span_from_word_range(
    segment: Dict[str, Any], i0: int, i1: int
) -> Tuple[int, int, str]:
    """
    Map inclusive word indices ``i0..i1`` to a char span into ``segment['text']``.

    Raises ``IndexError`` for out-of-range indices; ``ValueError`` if i1 < i0.
    """
    if i1 < i0:
        raise ValueError("word range end must be >= start")
    spans, _aligned = iter_segment_word_spans(segment)
    if not spans:
        raise IndexError("segment has no word spans")
    if i0 < 0 or i1 >= len(spans):
        raise IndexError(f"word range {i0}..{i1} out of bounds for {len(spans)} words")
    start = spans[i0].char_start
    end = spans[i1].char_end
    text = segment.get("text") or ""
    return start, end, text[start:end]


def find_unique_char_span(text: str, needle: str) -> Tuple[int, int]:
    """
    Resolve ``needle`` to an exact unique char span in ``text``.

    Raises ``ValueError`` if empty/not found; ``AmbiguousFindError`` if multiple.
    """
    if not needle:
        raise ValueError("find needle must be non-empty")
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    matches: List[Tuple[int, int]] = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            break
        matches.append((idx, idx + len(needle)))
        start = idx + 1
    if not matches:
        raise ValueError(f"Text {needle!r} not found in segment")
    if len(matches) > 1:
        raise AmbiguousFindError(needle, len(matches), matches)
    return matches[0]


def rebuild_untimed_words_from_text(text: str) -> List[Dict[str, Any]]:
    """Build untimed word dicts from whitespace tokens of ``text``."""
    return [{"word": tok, "start": None, "end": None} for _, _, tok in _whitespace_spans(text)]
