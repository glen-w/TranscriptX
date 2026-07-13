"""Consumer policies over shared PhraseQualityResult."""

from __future__ import annotations

from transcriptx.core.analysis.phrase_quality.types import (
    BORDERLINE_STOPWORD_RATIO,
    LIGHT_VERB_HEAD,
    LOW_CONTENT_RATIO,
    LOW_DISTINCTIVENESS,
    PhraseQualityResult,
    PolicyDecision,
    WEAK_BARE_NOUN,
)

# Preference tiers (lower is better).
TIER_MULTI_CONTENT_NOUN = 0
TIER_ENTITY_PROPN = 1
TIER_STRONG_SINGLE_NOUN = 2
TIER_VERB_LED = 3
TIER_OTHER = 4


def _preference_tier(result: PhraseQualityResult) -> int:
    feats = result.features
    if (
        feats.noun_headed
        and feats.content_token_count >= 2
        and WEAK_BARE_NOUN not in result.penalties
    ):
        return TIER_MULTI_CONTENT_NOUN
    if feats.has_entity or feats.has_propn:
        return TIER_ENTITY_PROPN
    if feats.noun_headed and feats.content_token_count >= 1:
        return TIER_STRONG_SINGLE_NOUN
    if feats.verb_headed and feats.content_token_count >= 2:
        return TIER_VERB_LED
    return TIER_OTHER


def _penalty_score(penalties: tuple[str, ...], *, weights: dict[str, float]) -> float:
    return float(sum(weights.get(code, 0.0) for code in penalties))


_THEME_PENALTY_WEIGHTS = {
    WEAK_BARE_NOUN: 0.40,
    LOW_CONTENT_RATIO: 0.25,
    LOW_DISTINCTIVENESS: 0.20,
    BORDERLINE_STOPWORD_RATIO: 0.15,
    LIGHT_VERB_HEAD: 0.20,
}

_CONTENT_PENALTY_WEIGHTS = {
    WEAK_BARE_NOUN: 0.20,
    LOW_CONTENT_RATIO: 0.15,
    LOW_DISTINCTIVENESS: 0.10,
    BORDERLINE_STOPWORD_RATIO: 0.10,
    LIGHT_VERB_HEAD: 0.05,
}

_HIGHLIGHT_PENALTY_WEIGHTS = {
    WEAK_BARE_NOUN: 0.15,
    LOW_CONTENT_RATIO: 0.10,
    LOW_DISTINCTIVENESS: 0.10,
    BORDERLINE_STOPWORD_RATIO: 0.08,
    LIGHT_VERB_HEAD: 0.10,
}


def theme_label_policy(result: PhraseQualityResult) -> PolicyDecision:
    """Summary key themes: prefer noun phrases; demote weak bare nouns."""
    if not result.accepted_for_scoring:
        return PolicyDecision(
            include=False,
            hard_reject_reason=result.hard_reject_reason,
            rank_penalty=0.0,
            preference_tier=TIER_OTHER,
            penalties=result.penalties,
        )
    tier = _preference_tier(result)
    # Theme labels: drop pure verb-led without noun partner (tier VERB_LED ok if
    # content_token_count >= 2 includes a noun via features — still allowed but
    # ranked worse). Reject LIGHT_VERB_HEAD-only singles.
    if result.features.verb_headed and result.features.content_token_count < 2:
        return PolicyDecision(
            include=False,
            hard_reject_reason=None,
            rank_penalty=1.0,
            preference_tier=tier,
            penalties=result.penalties,
        )
    # Weak bare noun: still includable for short transcripts, but heavily demoted.
    rank_penalty = _penalty_score(result.penalties, weights=_THEME_PENALTY_WEIGHTS)
    return PolicyDecision(
        include=True,
        hard_reject_reason=None,
        rank_penalty=rank_penalty,
        preference_tier=tier,
        penalties=result.penalties,
    )


def content_phrase_policy(result: PhraseQualityResult) -> PolicyDecision:
    """Insight eligibility: allow verb-led topical phrases; milder demotion."""
    if not result.accepted_for_scoring:
        return PolicyDecision(
            include=False,
            hard_reject_reason=result.hard_reject_reason,
            rank_penalty=0.0,
            preference_tier=TIER_OTHER,
            penalties=result.penalties,
        )
    # Require noun/propn head OR (non-light verb + at least one other content token).
    feats = result.features
    if feats.verb_headed and LIGHT_VERB_HEAD in result.penalties:
        if feats.content_token_count < 2:
            return PolicyDecision(
                include=False,
                hard_reject_reason=None,
                rank_penalty=1.0,
                preference_tier=TIER_OTHER,
                penalties=result.penalties,
            )
    if feats.head_pos not in {"NOUN", "PROPN", "VERB", None}:
        # Incomplete annotations: lexical accept if content tokens exist.
        if feats.annotations_complete:
            return PolicyDecision(
                include=False,
                hard_reject_reason=None,
                rank_penalty=1.0,
                preference_tier=TIER_OTHER,
                penalties=result.penalties,
            )
    rank_penalty = _penalty_score(result.penalties, weights=_CONTENT_PENALTY_WEIGHTS)
    return PolicyDecision(
        include=True,
        hard_reject_reason=None,
        rank_penalty=rank_penalty,
        preference_tier=_preference_tier(result),
        penalties=result.penalties,
    )


def highlight_label_policy(result: PhraseQualityResult) -> PolicyDecision:
    """Highlight theme labels: hard rejects only; broader soft fallback."""
    if not result.accepted_for_scoring:
        return PolicyDecision(
            include=False,
            hard_reject_reason=result.hard_reject_reason,
            rank_penalty=0.0,
            preference_tier=TIER_OTHER,
            penalties=result.penalties,
        )
    rank_penalty = _penalty_score(result.penalties, weights=_HIGHLIGHT_PENALTY_WEIGHTS)
    return PolicyDecision(
        include=True,
        hard_reject_reason=None,
        rank_penalty=rank_penalty,
        preference_tier=_preference_tier(result),
        penalties=result.penalties,
    )
