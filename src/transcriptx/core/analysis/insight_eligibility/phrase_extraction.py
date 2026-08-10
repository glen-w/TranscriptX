"""Phrase extraction with shared phrase-quality analyser."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Sequence, Set, Tuple

from transcriptx.core.analysis.phrase_quality import (
    analyse_phrase,
    content_phrase_policy,
)
from transcriptx.core.analysis.phrase_quality.analyser import annotations_from_surfaces
from transcriptx.core.analysis.phrase_quality.candidates import (
    annotations_from_spacy_span,
    token_annotations_from_spacy_token,
)
from transcriptx.core.analysis.phrase_quality.types import TokenAnnotation
from transcriptx.core.utils.nlp_runtime import get_nlp_model

from .content_filter import FilteredSegment
from .content_scoring import score_content_phrases


def _annotations_from_text(text: str) -> List[TokenAnnotation]:
    nlp = get_nlp_model()
    doc = nlp(text)
    out: List[TokenAnnotation] = []
    for tok in doc:
        ann = token_annotations_from_spacy_token(tok)
        if ann is not None:
            out.append(ann)
    if out:
        return out
    # Lexical fallback if spaCy yields nothing useful.
    surfaces = [t for t in text.casefold().split() if t.isalpha()]
    return annotations_from_surfaces(surfaces)


def _phrase_quality_from_result(result: Any) -> Dict[str, float]:
    feats = result.features
    if feats.head_pos in {"NOUN", "PROPN"}:
        pos_weight = 1.0
    elif feats.head_pos == "VERB":
        pos_weight = 0.9
    else:
        pos_weight = 0.7
    return {
        "stopword_ratio": float(feats.stopword_ratio),
        "content_token_ratio": float(feats.content_token_ratio),
        "pos_weight": pos_weight,
    }


def _passes_phrase_quality_gate(
    tokens_with_pos: Sequence[Tuple[str, str]],
    tic_mask: Set[str],
    *,
    stopword_ratio_threshold: float = 0.6,
) -> bool:
    """Compatibility wrapper used by tests; delegates to content_phrase policy."""
    if not tokens_with_pos:
        return False
    surfaces = [t for t, _ in tokens_with_pos]
    pos_tags = [p for _, p in tokens_with_pos]
    anns = annotations_from_surfaces(surfaces, pos_tags=pos_tags, lemmas=surfaces)
    result = analyse_phrase(anns, tic_mask=set(tic_mask))
    decision = content_phrase_policy(result)
    if not decision.include:
        return False
    if result.features.stopword_ratio > stopword_ratio_threshold:
        return False
    return True


def _extract_noun_chunks(
    segments: List[FilteredSegment], tic_mask: Set[str]
) -> List[Dict[str, Any]]:
    nlp = get_nlp_model()
    phrases: List[Dict[str, Any]] = []
    for segment in segments:
        doc = nlp(segment.raw_text)
        try:
            chunks = list(doc.noun_chunks)
        except Exception:
            chunks = []
        for chunk in chunks:
            anns = annotations_from_spacy_span(chunk)
            if not anns:
                continue
            result = analyse_phrase(anns, tic_mask=tic_mask)
            decision = content_phrase_policy(result)
            if not decision.include:
                continue
            phrase = result.features.display_form or result.features.canonical_key
            if phrase:
                quality = _phrase_quality_from_result(result)
                quality["rank_penalty"] = decision.rank_penalty
                quality["penalties"] = list(result.penalties)
                phrases.append({"phrase": phrase, "quality": quality})
    return phrases


def _extract_ngrams(
    segments: List[FilteredSegment],
    tic_mask: Set[str],
    *,
    min_frequency: int = 2,
) -> List[Dict[str, Any]]:
    counter: Counter[str] = Counter()
    quality_map: Dict[str, Dict[str, float]] = {}
    for segment in segments:
        tokens = _annotations_from_text(segment.raw_text)
        for n in (2, 3):
            for i in range(0, max(0, len(tokens) - n + 1)):
                ngram_tokens = tokens[i : i + n]
                result = analyse_phrase(ngram_tokens, tic_mask=tic_mask)
                decision = content_phrase_policy(result)
                if not decision.include:
                    continue
                phrase = result.features.display_form or result.features.canonical_key
                if phrase:
                    counter[phrase] += 1
                    if phrase not in quality_map:
                        quality = _phrase_quality_from_result(result)
                        quality["rank_penalty"] = decision.rank_penalty
                        quality["penalties"] = list(result.penalties)
                        quality_map[phrase] = quality
    phrases = [
        {"phrase": phrase, "quality": quality_map.get(phrase, {})}
        for phrase, freq in counter.items()
        if freq >= min_frequency
    ]
    phrases.sort(key=lambda row: str(row.get("phrase") or ""))
    return phrases


def extract_content_phrases(
    segments: List[FilteredSegment],
    *,
    tic_mask: Set[str],
    windows: List[Dict[str, Any]],
    speaker_blocks: List[Dict[str, Any]],
    entities: List[str] | None = None,
    min_frequency: int = 2,
    min_score: float = 0.28,
    require_spread_or_recurrence_for_singletons: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, float]]]:
    if not segments:
        return [], {}
    noun_chunks = _extract_noun_chunks(segments, tic_mask)
    ngrams = _extract_ngrams(segments, tic_mask, min_frequency=min_frequency)
    phrase_candidates = noun_chunks + ngrams
    if not phrase_candidates:
        return [], {}

    scores = score_content_phrases(
        phrase_candidates,
        windows=windows,
        speaker_blocks=speaker_blocks,
        entities=entities,
    )

    rows: List[Dict[str, Any]] = []
    for phrase, metrics in scores.items():
        if metrics["total"] < min_score:
            continue
        token_count = len([t for t in str(phrase).split() if t])
        if require_spread_or_recurrence_for_singletons and token_count <= 1:
            if float(metrics.get("spread", 0.0) or 0.0) <= 0.0 and float(
                metrics.get("recurrence", 0.0) or 0.0
            ) <= 0.0:
                continue
        rows.append({"phrase": phrase, "score": metrics})

    rows.sort(key=lambda row: (-row["score"]["total"], row["phrase"]))
    return rows, scores
