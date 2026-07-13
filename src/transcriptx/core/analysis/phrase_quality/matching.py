"""Token-boundary phrase matching helpers."""

from __future__ import annotations

from typing import Sequence

from transcriptx.core.analysis.phrase_quality.types import TokenAnnotation


def contiguous_lemma_window(
    tokens: Sequence[TokenAnnotation], start: int, length: int
) -> tuple[str, ...]:
    window = tokens[start : start + length]
    return tuple((tok.lemma or tok.surface).casefold() for tok in window)


def contiguous_surface_window(
    tokens: Sequence[TokenAnnotation], start: int, length: int
) -> tuple[str, ...]:
    window = tokens[start : start + length]
    return tuple(tok.surface.casefold() for tok in window)


def sequence_in_tokens(
    needles: set[tuple[str, ...]] | frozenset[tuple[str, ...]],
    tokens: Sequence[TokenAnnotation],
    *,
    use_lemma: bool = True,
) -> bool:
    """True if any needle matches a contiguous token-boundary window."""
    if not needles or not tokens:
        return False
    n = len(tokens)
    lengths = {len(needle) for needle in needles if needle}
    for length in lengths:
        if length <= 0 or length > n:
            continue
        for start in range(0, n - length + 1):
            if use_lemma:
                window = contiguous_lemma_window(tokens, start, length)
            else:
                window = contiguous_surface_window(tokens, start, length)
            if window in needles:
                return True
            # Also try surface when lemma path used (lexical fallback safety).
            if use_lemma:
                surface_window = contiguous_surface_window(tokens, start, length)
                if surface_window in needles:
                    return True
    return False


def exact_phrase_match(
    needles: set[tuple[str, ...]] | frozenset[tuple[str, ...]],
    tokens: Sequence[TokenAnnotation],
) -> bool:
    """Match only when the full phrase equals a needle (not a sub-window only)."""
    if not needles or not tokens:
        return False
    lemma_key = tuple((tok.lemma or tok.surface).casefold() for tok in tokens)
    surface_key = tuple(tok.surface.casefold() for tok in tokens)
    return lemma_key in needles or surface_key in needles


def strip_leading_determiners(lemmas: Sequence[str]) -> tuple[str, ...]:
    dets = {"the", "a", "an"}
    out = list(lemmas)
    while out and out[0] in dets:
        out.pop(0)
    return tuple(out)
