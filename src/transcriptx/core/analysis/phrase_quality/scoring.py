"""Deterministic theme scoring adjustments and sort keys."""

from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

from transcriptx.core.analysis.phrase_quality.types import (
    BORDERLINE_STOPWORD_RATIO,
    LIGHT_VERB_HEAD,
    LOW_CONTENT_RATIO,
    LOW_DISTINCTIVENESS,
    PhraseQualityResult,
    WEAK_BARE_NOUN,
)

# Named coefficients from the plan.
MULTI_CONTENT_NOUN_BONUS = 0.35
ENTITY_OR_PROPN_BONUS = 0.25
NOUN_CHUNK_SOURCE_BONUS = 0.15
WEAK_BARE_NOUN_PENALTY = 0.40
LOW_CONTENT_RATIO_PENALTY = 0.25
LOW_DISTINCTIVENESS_PENALTY = 0.20
BORDERLINE_STOPWORD_PENALTY = 0.15
LIGHT_VERB_HEAD_PENALTY = 0.20


def adjust_theme_score(
    base: float,
    result: PhraseQualityResult,
    *,
    source: str = "ngram",
    policy_rank_penalty: float = 0.0,
) -> float:
    """Apply deterministic bonuses/penalties to a base emblematic score."""
    feats = result.features
    adjusted = float(base)
    if feats.noun_headed and feats.content_token_count >= 2:
        adjusted += MULTI_CONTENT_NOUN_BONUS
    if feats.has_entity or feats.has_propn:
        adjusted += ENTITY_OR_PROPN_BONUS
    if source == "noun_chunk":
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
    adjusted -= float(policy_rank_penalty)
    return adjusted


def theme_sort_key(
    adjusted: float,
    result: PhraseQualityResult,
    *,
    preference_tier: int = 4,
) -> Tuple[Any, ...]:
    """Stable sort key: higher adjusted first, then richer phrases, then canonical."""
    feats = result.features
    return (
        preference_tier,
        -adjusted,
        -feats.content_token_count,
        -feats.token_count,
        feats.canonical_key,
    )


def near_duplicate(
    tokens_a: Sequence[str],
    tokens_b: Sequence[str],
    *,
    jaccard_threshold: float = 0.85,
) -> bool:
    a = {t.casefold() for t in tokens_a if t}
    b = {t.casefold() for t in tokens_b if t}
    if not a or not b:
        return False
    if a == b:
        return True
    if a.issubset(b) or b.issubset(a):
        return True
    union = a | b
    return (len(a & b) / float(len(union))) >= jaccard_threshold


def select_diverse_themes(
    candidates: Sequence[Dict[str, Any]],
    *,
    limit: int,
) -> list[Dict[str, Any]]:
    """Fill theme slots with lexical diversity; fewer bullets rather than padding."""
    selected: list[Dict[str, Any]] = []
    selected_keys: set[str] = set()
    used_heads: set[str] = set()

    def _is_dup(cand: Dict[str, Any]) -> bool:
        tokens = [str(t) for t in (cand.get("tokens") or [])]
        canonical = str(cand.get("canonical_key") or cand.get("phrase") or "")
        if canonical and canonical in selected_keys:
            return True
        for prev in selected:
            if near_duplicate(tokens, [str(t) for t in (prev.get("tokens") or [])]):
                return True
            if canonical and canonical == str(
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
