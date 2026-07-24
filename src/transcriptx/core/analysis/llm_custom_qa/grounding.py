"""Ground quotes against the grounding corpus (corpus-slice citations)."""

from __future__ import annotations

import unicodedata
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.bounded_input import (
    BoundedGroundingCorpus,
    SegmentMapEntry,
)
from transcriptx.core.analysis.llm_custom_qa.constants import (
    MAX_CITATIONS_PER_ANSWER,
    MAX_CROSS_SEGMENT_SPAN,
    MIN_RECOVERED_QUOTE_WORDS,
)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _ws_fold(text: str) -> str:
    """Whitespace-equivalence fold for matching only (case-sensitive source)."""
    return " ".join(_nfc(text).split())


def _build_ws_index(corpus: str) -> tuple[str, list[int]]:
    """Map folded corpus positions back to original corpus indices."""
    folded_chars: list[str] = []
    origins: list[int] = []
    i = 0
    n = len(corpus)
    while i < n:
        ch = corpus[i]
        if ch.isspace():
            while i < n and corpus[i].isspace():
                i += 1
            if folded_chars and folded_chars[-1] != " ":
                folded_chars.append(" ")
                origins.append(i - 1)
            continue
        folded_chars.append(ch)
        origins.append(i)
        i += 1
    # Trim trailing space
    if folded_chars and folded_chars[-1] == " ":
        folded_chars.pop()
        origins.pop()
    return "".join(folded_chars), origins


def _entries_for_span(
    entries: list[SegmentMapEntry], start: int, end: int
) -> list[SegmentMapEntry]:
    hit: list[SegmentMapEntry] = []
    for entry in entries:
        if entry.corpus_end <= start or entry.corpus_start >= end:
            continue
        hit.append(entry)
    return hit


def _find_matches(corpus: BoundedGroundingCorpus, quote: str) -> list[tuple[int, int]]:
    """Return contiguous corpus (start, end) matches using whitespace equivalence."""
    needle = _ws_fold(quote)
    if not needle:
        return []
    folded, origins = _build_ws_index(corpus.corpus_text)
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        pos = folded.find(needle, start)
        if pos < 0:
            break
        end_pos = pos + len(needle) - 1
        if end_pos >= len(origins) or pos >= len(origins):
            break
        corp_start = origins[pos]
        corp_end = origins[end_pos] + 1
        matches.append((corp_start, corp_end))
        start = pos + 1
    return matches


def _recover_groundable_quote(
    corpus: BoundedGroundingCorpus, quote: str
) -> Optional[str]:
    """Return the longest grounded contiguous word span inside a near-miss quote.

    Local models often prepend/append a few paraphrased words around a real
    transcript span. Recovering the grounded interior keeps cite-or-unavailable
    honest (citation text still comes from the corpus slice).
    """
    words = _ws_fold(quote).split()
    if len(words) < MIN_RECOVERED_QUOTE_WORDS:
        return None
    for n in range(len(words), MIN_RECOVERED_QUOTE_WORDS - 1, -1):
        for i in range(0, len(words) - n + 1):
            candidate = " ".join(words[i : i + n])
            if _find_matches(corpus, candidate):
                return candidate
    return None


def ground_answered_row(
    row: dict[str, Any],
    corpus: BoundedGroundingCorpus,
    *,
    max_citations: int = MAX_CITATIONS_PER_ANSWER,
) -> dict[str, Any]:
    """Ground an answered row; on failure convert to unavailable/grounding_failed."""
    quotes = list(row.get("_model_quotes") or [])
    grounding = {
        "quotes_requested": len(quotes),
        "quotes_grounded": 0,
        "citations_emitted": 0,
        "citations_truncated": 0,
        "cross_segment_citations": 0,
    }
    citations: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, tuple[int, ...]]] = set()
    omitted = 0

    for quote in quotes:
        matches = _find_matches(corpus, quote)
        if not matches:
            recovered = _recover_groundable_quote(corpus, quote)
            if recovered is not None:
                matches = _find_matches(corpus, recovered)
        grounded_any = False
        for corp_start, corp_end in matches:
            entries = _entries_for_span(corpus.entries, corp_start, corp_end)
            if not entries:
                continue
            if len(entries) > MAX_CROSS_SEGMENT_SPAN:
                continue
            # Contiguous canonical indexes required
            idxs = [e.canonical_index for e in entries]
            if idxs != list(range(idxs[0], idxs[0] + len(idxs))):
                continue
            original_indexes = [e.original_segment_index for e in entries]
            slice_quote = corpus.corpus_text[corp_start:corp_end]
            key = (slice_quote, tuple(original_indexes))
            if key in seen_keys:
                continue
            grounded_any = True
            if len(citations) >= max_citations:
                omitted += 1
                continue
            seen_keys.add(key)
            start_time = entries[0].start_time
            end_time = entries[-1].end_time
            citations.append(
                {
                    "quote": slice_quote,
                    "segment_indexes": original_indexes,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            if len(entries) > 1:
                grounding["cross_segment_citations"] += 1
        if grounded_any:
            grounding["quotes_grounded"] += 1

    grounding["citations_emitted"] = len(citations)
    grounding["citations_truncated"] = omitted

    if not citations:
        out = dict(row)
        out["status"] = "unavailable"
        out["answer"] = None
        out["abstain_reason"] = None
        out["system_reason"] = "grounding_failed"
        out["confidence"] = None
        out["citations"] = []
        out["grounding"] = grounding
        return out

    out = dict(row)
    out["citations"] = citations
    out["grounding"] = grounding
    return out


def apply_grounding(
    answers: list[dict[str, Any]],
    corpus: BoundedGroundingCorpus,
    *,
    diagnostics: dict[str, int],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in answers:
        if row.get("status") != "answered":
            out.append(row)
            continue
        grounded = ground_answered_row(row, corpus)
        if grounded.get("system_reason") == "grounding_failed":
            diagnostics["grounding_failed_count"] = (
                int(diagnostics.get("grounding_failed_count", 0)) + 1
            )
        diagnostics["citations_total"] = int(
            diagnostics.get("citations_total", 0)
        ) + len(grounded.get("citations") or [])
        diagnostics["cross_segment_citations_total"] = int(
            diagnostics.get("cross_segment_citations_total", 0)
        ) + int((grounded.get("grounding") or {}).get("cross_segment_citations", 0))
        out.append(grounded)
    return out


def apply_soft_grounding(
    answers: list[dict[str, Any]],
    corpus: BoundedGroundingCorpus,
    *,
    diagnostics: dict[str, int],
) -> list[dict[str, Any]]:
    """Attach citations when quotes match; never kill answered rows for miss."""
    out: list[dict[str, Any]] = []
    for row in answers:
        if row.get("status") != "answered":
            out.append(row)
            continue
        grounded = ground_answered_row(row, corpus)
        if grounded.get("system_reason") == "grounding_failed":
            soft = dict(row)
            soft["citations"] = []
            soft_grounding = dict(grounded.get("grounding") or {})
            soft_grounding["quotes_soft_dropped"] = int(
                soft_grounding.get("quotes_requested", 0)
            )
            soft["grounding"] = soft_grounding
            soft.pop("system_reason", None)
            diagnostics["soft_quote_drops"] = int(
                diagnostics.get("soft_quote_drops", 0)
            ) + int(soft_grounding.get("quotes_requested", 0))
            out.append(soft)
            continue
        diagnostics["citations_total"] = int(
            diagnostics.get("citations_total", 0)
        ) + len(grounded.get("citations") or [])
        diagnostics["cross_segment_citations_total"] = int(
            diagnostics.get("cross_segment_citations_total", 0)
        ) + int((grounded.get("grounding") or {}).get("cross_segment_citations", 0))
        out.append(grounded)
    return out
