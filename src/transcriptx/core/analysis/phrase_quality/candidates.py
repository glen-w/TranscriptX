"""Candidate generation helpers: n-grams, noun chunks, entities from parsed docs."""

from __future__ import annotations

from typing import Any, Iterable, List, Sequence

from transcriptx.core.analysis.phrase_quality.matching import strip_leading_determiners
from transcriptx.core.analysis.phrase_quality.types import TokenAnnotation


def token_annotations_from_spacy_token(tok: Any) -> TokenAnnotation | None:
    if not getattr(tok, "is_alpha", False):
        return None
    surface = str(tok.text or "").casefold().strip()
    if not surface:
        return None
    lemma = str(getattr(tok, "lemma_", surface) or surface).casefold().strip()
    pos = str(getattr(tok, "pos_", "") or "") or None
    is_stop = bool(getattr(tok, "is_stop", False))
    ent_type = str(getattr(tok, "ent_type_", "") or "") or None
    return TokenAnnotation(
        surface=surface,
        lemma=lemma or surface,
        pos=pos,
        is_stop=is_stop,
        ent_type=ent_type if ent_type else None,
    )


def annotations_from_spacy_span(span: Any) -> list[TokenAnnotation]:
    out: list[TokenAnnotation] = []
    for tok in span:
        ann = token_annotations_from_spacy_token(tok)
        if ann is not None:
            out.append(ann)
    return out


def annotations_from_spacy_doc(doc: Any) -> list[TokenAnnotation]:
    return annotations_from_spacy_span(doc)


def iter_ngram_spans(
    tokens: Sequence[TokenAnnotation], min_len: int, max_len: int
) -> Iterable[tuple[int, int, list[TokenAnnotation]]]:
    n = len(tokens)
    for length in range(min_len, max_len + 1):
        for start in range(0, max(0, n - length + 1)):
            yield start, start + length, list(tokens[start : start + length])


def canonical_key_from_annotations(tokens: Sequence[TokenAnnotation]) -> str:
    lemmas = [(tok.lemma or tok.surface).casefold() for tok in tokens]
    stripped = strip_leading_determiners(lemmas)
    return " ".join(stripped) if stripped else " ".join(lemmas)


def display_form_from_annotations(tokens: Sequence[TokenAnnotation]) -> str:
    return " ".join(tok.surface for tok in tokens)


def merge_candidate_stats(
    store: dict[str, dict[str, Any]],
    *,
    tokens: list[TokenAnnotation],
    source: str,
    speaker: str,
    start: float,
    end: float,
    example: Any,
    tfidf: float | None,
) -> None:
    """Accumulate stats keyed by canonical identity; keep dominant display form."""
    if not tokens:
        return
    key = canonical_key_from_annotations(tokens)
    if not key:
        return
    display = display_form_from_annotations(tokens)
    stats = store.setdefault(
        key,
        {
            "canonical_key": key,
            "display_counts": {},
            "tokens": [t.surface for t in tokens],
            "annotations": tokens,
            "count": 0,
            "speakers": set(),
            "first_seen": start,
            "last_seen": end,
            "examples": [],
            "tfidf_scores": [],
            "sources": set(),
            "has_entity": any(bool(t.ent_type) for t in tokens),
            "has_propn": any(t.pos == "PROPN" for t in tokens),
        },
    )
    stats["count"] += 1
    stats["speakers"].add(speaker)
    stats["first_seen"] = min(stats["first_seen"], start)
    stats["last_seen"] = max(stats["last_seen"], end)
    stats["examples"].append(example)
    stats["sources"].add(source)
    stats["display_counts"][display] = stats["display_counts"].get(display, 0) + 1
    # Prefer longer / entity-linked annotations as representative.
    if len(tokens) > len(stats["annotations"]) or (
        any(bool(t.ent_type) for t in tokens) and not stats["has_entity"]
    ):
        stats["annotations"] = tokens
        stats["tokens"] = [t.surface for t in tokens]
    stats["has_entity"] = stats["has_entity"] or any(bool(t.ent_type) for t in tokens)
    stats["has_propn"] = stats["has_propn"] or any(t.pos == "PROPN" for t in tokens)
    if tfidf is not None:
        stats["tfidf_scores"].append(tfidf)


def dominant_display(stats: dict[str, Any]) -> str:
    counts: dict[str, int] = stats.get("display_counts") or {}
    if not counts:
        return str(stats.get("canonical_key") or "")
    # Most frequent display; tie-break lexicographic for stability.
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def cluster_prefer_longer(
    candidates: List[dict[str, Any]],
    *,
    jaccard_threshold: float = 0.85,
) -> List[dict[str, Any]]:
    """Resolve near-duplicates preferring longer / entity-linked phrases."""
    ranked = sorted(
        candidates,
        key=lambda c: (
            -int(bool(c.get("has_entity") or c.get("has_propn"))),
            -len(c.get("tokens") or []),
            -float((c.get("score") or {}).get("total") or 0.0),
            str(c.get("canonical_key") or c.get("phrase") or ""),
        ),
    )
    kept: List[dict[str, Any]] = []
    for cand in ranked:
        tokens = set(str(t).casefold() for t in (cand.get("tokens") or []))
        key = str(cand.get("canonical_key") or cand.get("phrase") or "")
        drop = False
        for existing in kept:
            et = set(str(t).casefold() for t in (existing.get("tokens") or []))
            ek = str(existing.get("canonical_key") or existing.get("phrase") or "")
            if key == ek:
                drop = True
                break
            if not tokens or not et:
                continue
            overlap = len(tokens & et) / float(len(tokens | et))
            contains = tokens.issubset(et) or et.issubset(tokens)
            if overlap >= jaccard_threshold or contains:
                drop = True
                break
        if not drop:
            kept.append(cand)
    return kept
