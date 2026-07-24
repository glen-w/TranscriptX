"""Noun-chunk candidate extraction from insight_eligibility filtered segments."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.keyphrases import phrase_quality_adapter as adapter
from transcriptx.core.analysis.keyphrases.contract import (
    PhraseEvidence,
    RankedPhrase,
)
from transcriptx.core.analysis.keyphrases.scoring import (
    assign_ranks_and_weights,
    base_salience,
    length_ok,
)
from transcriptx.core.analysis.wordclouds.output_bridge import (
    _include_speaker_wordcloud,
)


def _segment_id(seg: dict[str, Any], index: int) -> str:
    for key in ("segment_id", "id", "uid"):
        val = seg.get(key)
        if val is not None and str(val).strip():
            return str(val)
    return f"seg-{index}"


def _snippet(text: str, max_chars: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _accumulate_chunk(
    store: dict[str, dict[str, Any]],
    *,
    tokens: list,
    speaker: str,
    segment_id: str,
    start: float | None,
    end: float | None,
    snippet: str | None,
    evidence_max: int,
) -> None:
    if not tokens:
        return
    key = adapter.canonical_key(tokens)
    if not key:
        return
    display = adapter.display_form(tokens)
    entry = store.setdefault(
        key,
        {
            "canonical_key": key,
            "display_counts": {},
            "tokens": [t.surface for t in tokens],
            "annotations": tokens,
            "occurrence_count": 0,
            "segment_ids": set(),
            "evidence": [],
            "head_lemma": "",
        },
    )
    entry["occurrence_count"] += 1
    entry["segment_ids"].add(segment_id)
    entry["display_counts"][display] = entry["display_counts"].get(display, 0) + 1
    if len(tokens) >= len(entry["annotations"]):
        entry["annotations"] = tokens
        entry["tokens"] = [t.surface for t in tokens]
        if tokens:
            entry["head_lemma"] = str(
                getattr(tokens[-1], "lemma", None) or tokens[-1].surface or ""
            )
    if len(entry["evidence"]) < evidence_max:
        entry["evidence"].append(
            PhraseEvidence(
                segment_id=segment_id,
                speaker_id=speaker or None,
                start=start,
                end=end,
                snippet=snippet,
            )
        )


def _dominant_display(entry: dict[str, Any]) -> str:
    counts: dict[str, int] = entry.get("display_counts") or {}
    if not counts:
        return str(entry.get("canonical_key") or "")
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def extract_noun_chunk_stores(
    filtered_segments: list[dict[str, Any]],
    *,
    nlp: Any,
    min_phrase_tokens: int,
    max_phrase_tokens: int,
    evidence_max_per_phrase: int,
    evidence_snippet_max_chars: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    """Return (global_store, speaker_stores) accumulated per segment (no cross-segment)."""
    global_store: dict[str, dict[str, Any]] = {}
    speaker_stores: dict[str, dict[str, dict[str, Any]]] = {}

    for idx, seg in enumerate(filtered_segments):
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("content_text") or seg.get("text") or "").strip()
        if not text:
            continue
        speaker = str(seg.get("speaker") or "").strip()
        seg_id = _segment_id(seg, idx)
        start = seg.get("start")
        end = seg.get("end")
        start_f = float(start) if isinstance(start, (int, float)) else None
        end_f = float(end) if isinstance(end, (int, float)) else None
        snippet = _snippet(text, evidence_snippet_max_chars)
        try:
            doc = nlp(text)
        except Exception:
            continue
        for chunk in getattr(doc, "noun_chunks", ()) or ():
            tokens = adapter.span_to_annotations(chunk)
            if not length_ok(
                len(tokens),
                min_tokens=min_phrase_tokens,
                max_tokens=max_phrase_tokens,
            ):
                continue
            _accumulate_chunk(
                global_store,
                tokens=tokens,
                speaker=speaker,
                segment_id=seg_id,
                start=start_f,
                end=end_f,
                snippet=snippet,
                evidence_max=evidence_max_per_phrase,
            )
            if speaker and _include_speaker_wordcloud(speaker):
                sp_store = speaker_stores.setdefault(speaker, {})
                _accumulate_chunk(
                    sp_store,
                    tokens=tokens,
                    speaker=speaker,
                    segment_id=seg_id,
                    start=start_f,
                    end=end_f,
                    snippet=snippet,
                    evidence_max=evidence_max_per_phrase,
                )

    return global_store, speaker_stores


def store_to_ranked(
    store: dict[str, dict[str, Any]],
    *,
    language: str | None,
    min_occurrences: int,
    max_phrases: int,
    diversity_jaccard_threshold: float,
) -> list[RankedPhrase]:
    candidates: list[dict[str, Any]] = []
    for entry in store.values():
        occ = int(entry.get("occurrence_count") or 0)
        if occ < min_occurrences:
            continue
        annotations = entry.get("annotations") or []
        quality = adapter.analyse_candidate(annotations, language=language)
        base = base_salience(
            occurrence_count=occ,
            segment_support=len(entry.get("segment_ids") or ()),
            token_count=len(annotations),
        )
        adjusted = adapter.quality_adjust(base, quality)
        if adjusted <= 0:
            continue
        candidates.append(
            {
                "canonical_key": entry["canonical_key"],
                "phrase": _dominant_display(entry),
                "tokens": list(entry.get("tokens") or []),
                "head_lemma": entry.get("head_lemma") or "",
                "token_count": len(annotations),
                "raw_score": float(adjusted),
                "occurrence_count": occ,
                "segment_support": len(entry.get("segment_ids") or ()),
                "evidence": list(entry.get("evidence") or []),
            }
        )

    candidates.sort(
        key=lambda c: (
            -float(c["raw_score"]),
            -int(c["occurrence_count"]),
            -int(c["token_count"]),
            str(c["canonical_key"]),
        )
    )
    diversified = adapter.apply_diversity(
        candidates,
        limit=max_phrases,
        jaccard_threshold=diversity_jaccard_threshold,
    )
    phrases = [
        RankedPhrase(
            phrase=str(c["phrase"]),
            canonical_key=str(c["canonical_key"]),
            token_count=int(c["token_count"]),
            rank=1,
            raw_score=float(c["raw_score"]),
            score_direction="higher_is_better",
            rank_weight=0.0,
            occurrence_count=int(c["occurrence_count"]),
            segment_support=int(c["segment_support"]),
            evidence=list(c.get("evidence") or []),
        )
        for c in diversified
    ]
    return assign_ranks_and_weights(phrases)
