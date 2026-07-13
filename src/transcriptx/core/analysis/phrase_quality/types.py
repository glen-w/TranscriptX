"""Types for shared phrase quality analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Hard reject reason codes
EMPTY = "EMPTY"
ALL_STOPWORDS = "ALL_STOPWORDS"
DISCOURSE_FORMULA = "DISCOURSE_FORMULA"
LIGHT_VERB_CONSTRUCTION = "LIGHT_VERB_CONSTRUCTION"
TIC_OR_DISCOURSE_MASK = "TIC_OR_DISCOURSE_MASK"
PRONOUN_SHARD = "PRONOUN_SHARD"
NO_CONTENT_TOKEN = "NO_CONTENT_TOKEN"
SHORT_TOKEN_SHARD = "SHORT_TOKEN_SHARD"

# Soft penalty codes
WEAK_BARE_NOUN = "WEAK_BARE_NOUN"
LOW_CONTENT_RATIO = "LOW_CONTENT_RATIO"
LOW_DISTINCTIVENESS = "LOW_DISTINCTIVENESS"
BORDERLINE_STOPWORD_RATIO = "BORDERLINE_STOPWORD_RATIO"
LIGHT_VERB_HEAD = "LIGHT_VERB_HEAD"


@dataclass(frozen=True)
class TokenAnnotation:
    """Pre-tokenised annotation from an already-parsed document."""

    surface: str
    lemma: str
    pos: Optional[str] = None
    is_stop: Optional[bool] = None
    ent_type: Optional[str] = None


@dataclass(frozen=True)
class PhraseFeatures:
    surfaces: tuple[str, ...]
    lemmas: tuple[str, ...]
    pos_tags: tuple[Optional[str], ...]
    token_count: int
    content_token_count: int
    stopword_ratio: float
    content_token_ratio: float
    head_lemma: Optional[str]
    head_pos: Optional[str]
    has_entity: bool
    has_propn: bool
    noun_headed: bool
    verb_headed: bool
    is_weak_bare_noun: bool
    annotations_complete: bool
    language: str
    canonical_key: str
    display_form: str


@dataclass(frozen=True)
class PhraseQualityResult:
    """Structured analyser output: hard reject vs soft penalties."""

    accepted_for_scoring: bool
    hard_reject_reason: Optional[str]
    penalties: tuple[str, ...]
    features: PhraseFeatures


@dataclass(frozen=True)
class PolicyDecision:
    """Consumer-specific include/exclude decision on top of analyser output."""

    include: bool
    hard_reject_reason: Optional[str]
    rank_penalty: float
    preference_tier: int
    penalties: tuple[str, ...]
