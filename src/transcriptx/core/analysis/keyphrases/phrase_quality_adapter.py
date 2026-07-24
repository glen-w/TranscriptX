"""Keyphrases-owned phrase_quality adapter (frozen semantics, not theme API)."""

from __future__ import annotations

from typing import Any, Sequence

from transcriptx.core.analysis.phrase_quality.analyser import analyse_phrase
from transcriptx.core.analysis.phrase_quality.candidates import (
    annotations_from_spacy_span,
    canonical_key_from_annotations,
    display_form_from_annotations,
)
from transcriptx.core.analysis.phrase_quality.scoring import near_duplicate
from transcriptx.core.analysis.phrase_quality.types import (
    BORDERLINE_STOPWORD_RATIO,
    LIGHT_VERB_HEAD,
    LOW_CONTENT_RATIO,
    LOW_DISTINCTIVENESS,
    PhraseQualityResult,
    TokenAnnotation,
    WEAK_BARE_NOUN,
)

# Versioned keyphrases coefficients (may match theme numbers initially).
KEYPHRASES_ADAPTER_VERSION = 1
MULTI_CONTENT_NOUN_BONUS = 0.35
ENTITY_OR_PROPN_BONUS = 0.25
NOUN_CHUNK_SOURCE_BONUS = 0.15
WEAK_BARE_NOUN_PENALTY = 0.40
LOW_CONTENT_RATIO_PENALTY = 0.25
LOW_DISTINCTIVENESS_PENALTY = 0.20
BORDERLINE_STOPWORD_PENALTY = 0.15
LIGHT_VERB_HEAD_PENALTY = 0.20


def span_to_annotations(span: Any) -> list[TokenAnnotation]:
    return annotations_from_spacy_span(span)


def canonical_key(tokens: Sequence[TokenAnnotation]) -> str:
    return canonical_key_from_annotations(list(tokens))


def display_form(tokens: Sequence[TokenAnnotation]) -> str:
    return display_form_from_annotations(list(tokens))


def analyse_candidate(
    tokens: Sequence[TokenAnnotation],
    *,
    language: str | None = None,
) -> PhraseQualityResult:
    return analyse_phrase(list(tokens), language=language)


def quality_adjust(base_score: float, result: PhraseQualityResult) -> float:
    """Keyphrases-named quality adjustment (not theme public API)."""
    if result.hard_reject:
        return 0.0
    feats = result.features
    adjusted = float(base_score)
    if feats.noun_headed and feats.content_token_count >= 2:
        adjusted += MULTI_CONTENT_NOUN_BONUS
    if feats.has_entity or feats.has_propn:
        adjusted += ENTITY_OR_PROPN_BONUS
    adjusted += NOUN_CHUNK_SOURCE_BONUS
    penalties = set(result.penalties)
    if WEAK_BARE_NOUN in penalties:
        adjusted -= WEAK_BARE_NOUN_PENALTY
    if LOW_CONTENT_RATIO in penalties:
        adjusted -= LOW_CONTENT_RATIO_PENALTY
    if LOW_DISTINCTIVENESS in penalties:
        adjusted -= LOW_DISTINCTIVENESS_PENALTY
    if BORDERLINE_STOPWORD_RATIO in penalties:
        adjusted -= BORDERLINE_STOPWORD_PENALTY
    if LIGHT_VERB_HEAD in penalties:
        adjusted -= LIGHT_VERB_HEAD_PENALTY
    return adjusted


def apply_diversity(
    candidates: Sequence[dict[str, Any]],
    *,
    limit: int,
    jaccard_threshold: float,
) -> list[dict[str, Any]]:
    """Diversity filter with frozen keyphrases semantics (head + near-dup)."""
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    used_heads: set[str] = set()

    def _is_dup(cand: dict[str, Any]) -> bool:
        tokens = [str(t) for t in (cand.get("tokens") or [])]
        key = str(cand.get("canonical_key") or cand.get("phrase") or "")
        if key and key in selected_keys:
            return True
        for prev in selected:
            if near_duplicate(
                tokens,
                [str(t) for t in (prev.get("tokens") or [])],
                jaccard_threshold=jaccard_threshold,
            ):
                return True
            if key and key == str(
                prev.get("canonical_key") or prev.get("phrase") or ""
            ):
                return True
        return False

    for cand in candidates:
        if len(selected) >= limit:
            break
        if _is_dup(cand):
            continue
        head = str(cand.get("head_lemma") or "")
        if head and head in used_heads:
            continue
        selected.append(cand)
        key = str(cand.get("canonical_key") or cand.get("phrase") or "")
        if key:
            selected_keys.add(key)
        if head:
            used_heads.add(head)

    if len(selected) < limit:
        for cand in candidates:
            if len(selected) >= limit:
                break
            key = str(cand.get("canonical_key") or cand.get("phrase") or "")
            if key and key in selected_keys:
                continue
            if _is_dup(cand):
                continue
            selected.append(cand)
            if key:
                selected_keys.add(key)

    return selected
