"""Shared phrase analyser: structured features, hard rejects, soft penalties."""

from __future__ import annotations

from typing import Optional, Sequence

from transcriptx.core.analysis.phrase_quality.matching import (
    exact_phrase_match,
    strip_leading_determiners,
)
from transcriptx.core.analysis.phrase_quality.resources import (
    ThemePhraseResources,
    load_theme_phrase_resources,
    normalize_phrase_text,
)
from transcriptx.core.analysis.phrase_quality.types import (
    ALL_STOPWORDS as REASON_ALL_STOPWORDS,
    BORDERLINE_STOPWORD_RATIO,
    DISCOURSE_FORMULA,
    EMPTY,
    LIGHT_VERB_CONSTRUCTION,
    LIGHT_VERB_HEAD,
    LOW_CONTENT_RATIO,
    LOW_DISTINCTIVENESS,
    NO_CONTENT_TOKEN,
    PRONOUN_SHARD,
    PhraseFeatures,
    PhraseQualityResult,
    SHORT_TOKEN_SHARD,
    TIC_OR_DISCOURSE_MASK,
    TokenAnnotation,
    WEAK_BARE_NOUN,
)
from transcriptx.core.utils.nlp_utils import (
    DISCOURSE_HEDGE_TERMS,
    get_all_stopwords,
)

# Bump when analyser semantics change (cache / schema invalidation).
PHRASE_QUALITY_VERSION = 3

_FUNCTION_POS = frozenset(
    {"PRON", "DET", "ADP", "CCONJ", "SCONJ", "PART", "INTJ", "AUX"}
)
_CONTENT_POS = frozenset({"NOUN", "PROPN", "VERB"})
_ALLOWED_ACRONYMS = frozenset({"ai", "ml", "ui", "ux"})


def annotations_from_surfaces(
    surfaces: Sequence[str],
    *,
    lemmas: Sequence[str] | None = None,
    pos_tags: Sequence[Optional[str]] | None = None,
    is_stop: Sequence[Optional[bool]] | None = None,
    ent_types: Sequence[Optional[str]] | None = None,
) -> list[TokenAnnotation]:
    """Build annotations without spaCy; used for lexical fallback / tests."""
    out: list[TokenAnnotation] = []
    for idx, surface in enumerate(surfaces):
        norm = normalize_phrase_text(surface)
        if not norm:
            continue
        lemma = (
            normalize_phrase_text(lemmas[idx])
            if lemmas is not None and idx < len(lemmas)
            else norm
        )
        pos = pos_tags[idx] if pos_tags is not None and idx < len(pos_tags) else None
        stop = is_stop[idx] if is_stop is not None and idx < len(is_stop) else None
        ent = ent_types[idx] if ent_types is not None and idx < len(ent_types) else None
        out.append(
            TokenAnnotation(
                surface=norm,
                lemma=lemma or norm,
                pos=pos,
                is_stop=stop,
                ent_type=ent,
            )
        )
    return out


def _is_english(language: str | None) -> bool:
    # Unknown defaults to English (current product behaviour for this pass).
    if not language:
        return True
    lang = language.casefold().strip()
    return lang in {"en", "eng", "english", "en-us", "en-gb", "unknown"}


def _token_is_stop(tok: TokenAnnotation, stopwords: set[str]) -> bool:
    if tok.is_stop is not None:
        return bool(tok.is_stop)
    return tok.surface in stopwords or tok.lemma in stopwords


def _is_content_token(
    tok: TokenAnnotation,
    *,
    stopwords: set[str],
    tic_mask: set[str],
    annotations_complete: bool,
) -> bool:
    surface = tok.surface
    lemma = tok.lemma or surface
    if len(surface) <= 1 and surface not in _ALLOWED_ACRONYMS:
        return False
    if surface in tic_mask or lemma in tic_mask:
        return False
    if surface in DISCOURSE_HEDGE_TERMS or lemma in DISCOURSE_HEDGE_TERMS:
        return False
    if annotations_complete and tok.pos:
        if tok.pos in _FUNCTION_POS:
            return False
        if tok.pos in _CONTENT_POS:
            return True
        if _token_is_stop(tok, stopwords) and tok.pos not in _CONTENT_POS:
            return False
        return tok.pos in _CONTENT_POS
    # Lexical fallback when POS missing.
    return not _token_is_stop(tok, stopwords)


def _head_index(
    tokens: Sequence[TokenAnnotation], *, annotations_complete: bool
) -> int:
    if annotations_complete:
        for idx, tok in enumerate(tokens):
            if tok.pos in {"NOUN", "PROPN"}:
                return idx
        for idx, tok in enumerate(tokens):
            if tok.pos == "VERB":
                return idx
    return max(0, len(tokens) - 1)


def _is_light_verb_construction(
    tokens: Sequence[TokenAnnotation],
    resources: ThemePhraseResources,
) -> bool:
    if len(tokens) < 2:
        return False
    lemmas = [(tok.lemma or tok.surface).casefold() for tok in tokens]
    surfaces = [tok.surface.casefold() for tok in tokens]

    def _is_lv(token: str) -> bool:
        return token in resources.light_verbs

    # Contiguous light_verb + to anywhere in the phrase (need to, going to, need to decide).
    for idx in range(len(tokens) - 1):
        left_l, right_l = lemmas[idx], lemmas[idx + 1]
        left_s, right_s = surfaces[idx], surfaces[idx + 1]
        if _is_lv(left_l) and right_l == "to":
            return True
        if _is_lv(left_s) and right_s == "to":
            return True

    # pronoun + light_verb — only exact 2-token phrases
    if len(tokens) == 2:
        subj, verb = lemmas[0], lemmas[1]
        if subj in resources.pronoun_subjects and verb in resources.light_verbs:
            return True
        if (
            surfaces[0] in resources.pronoun_subjects
            and surfaces[1] in resources.light_verbs
        ):
            return True
    return False


def _is_short_token_shard(tokens: Sequence[TokenAnnotation]) -> bool:
    if not tokens:
        return True
    if (
        len(tokens) == 1
        and len(tokens[0].surface) <= 2
        and tokens[0].surface not in _ALLOWED_ACRONYMS
    ):
        return True
    if len(tokens) > 1 and all(
        len(tok.surface) <= 2 and tok.surface not in _ALLOWED_ACRONYMS for tok in tokens
    ):
        return True
    return False


def _is_prep_discourse_noun(
    tokens: Sequence[TokenAnnotation], resources: ThemePhraseResources
) -> bool:
    if len(tokens) != 2:
        return False
    left = (tokens[0].lemma or tokens[0].surface).casefold()
    right = (tokens[1].lemma or tokens[1].surface).casefold()
    if (
        left in {"of", "for", "in", "at", "by", "as"}
        and right in resources.discourse_nouns
    ):
        return True
    return False


def _is_pronoun_shard(
    tokens: Sequence[TokenAnnotation],
    *,
    stopwords: set[str],
    annotations_complete: bool,
) -> bool:
    if not tokens:
        return True
    if annotations_complete and all(
        (tok.pos in _FUNCTION_POS) or _token_is_stop(tok, stopwords) for tok in tokens
    ):
        # Allow if any content POS slipped through
        if any(tok.pos in _CONTENT_POS for tok in tokens):
            return False
        return True
    if all(_token_is_stop(tok, stopwords) for tok in tokens):
        return True
    return False


def _canonical_key(tokens: Sequence[TokenAnnotation]) -> str:
    lemmas = [(tok.lemma or tok.surface).casefold() for tok in tokens]
    stripped = strip_leading_determiners(lemmas)
    return " ".join(stripped) if stripped else " ".join(lemmas)


def analyse_phrase(
    tokens: Sequence[TokenAnnotation],
    *,
    tic_mask: set[str] | None = None,
    resources: ThemePhraseResources | None = None,
    language: str | None = None,
    distinctiveness: float | None = None,
) -> PhraseQualityResult:
    """Analyse a candidate phrase from pre-tokenised annotations (no spaCy reparse)."""
    stopwords = get_all_stopwords()
    mask = tic_mask if tic_mask is not None else set()
    res = resources or load_theme_phrase_resources()
    lang = (language or "en").casefold()
    english = _is_english(lang)

    if not tokens:
        empty_features = PhraseFeatures(
            surfaces=(),
            lemmas=(),
            pos_tags=(),
            token_count=0,
            content_token_count=0,
            stopword_ratio=1.0,
            content_token_ratio=0.0,
            head_lemma=None,
            head_pos=None,
            has_entity=False,
            has_propn=False,
            noun_headed=False,
            verb_headed=False,
            is_weak_bare_noun=False,
            annotations_complete=False,
            language=lang,
            canonical_key="",
            display_form="",
        )
        return PhraseQualityResult(
            accepted_for_scoring=False,
            hard_reject_reason=EMPTY,
            penalties=(),
            features=empty_features,
        )

    annotations_complete = all(tok.pos is not None for tok in tokens)
    surfaces = tuple(tok.surface for tok in tokens)
    lemmas = tuple((tok.lemma or tok.surface).casefold() for tok in tokens)
    pos_tags = tuple(tok.pos for tok in tokens)
    display_form = " ".join(surfaces)
    canonical = _canonical_key(tokens)

    stop_count = sum(1 for tok in tokens if _token_is_stop(tok, stopwords))
    stopword_ratio = float(stop_count) / float(len(tokens))
    content_tokens = [
        tok
        for tok in tokens
        if _is_content_token(
            tok,
            stopwords=stopwords,
            tic_mask=mask,
            annotations_complete=annotations_complete,
        )
    ]
    content_token_count = len(content_tokens)
    content_token_ratio = float(content_token_count) / float(len(tokens))

    hidx = _head_index(tokens, annotations_complete=annotations_complete)
    head = tokens[hidx]
    head_lemma = (head.lemma or head.surface).casefold()
    head_pos = head.pos
    has_entity = any(bool(tok.ent_type) for tok in tokens)
    has_propn = any(tok.pos == "PROPN" for tok in tokens) or has_entity
    noun_headed = bool(head_pos in {"NOUN", "PROPN"}) or (
        not annotations_complete and content_token_count > 0 and head_pos is None
    )
    verb_headed = head_pos == "VERB"

    # Weak bare noun: optional DET + single common/generic NOUN, no entity/PROPN.
    lemmas_stripped = strip_leading_determiners(lemmas)
    is_weak_bare_noun = False
    if (
        len(lemmas_stripped) == 1
        and not has_propn
        and not has_entity
        and lemmas_stripped[0] not in _ALLOWED_ACRONYMS
    ):
        sole = lemmas_stripped[0]
        generic = sole in res.discourse_nouns or len(sole) <= 3
        if annotations_complete:
            content_pos = [tok.pos for tok in tokens if tok.pos in _CONTENT_POS]
            if generic and (
                content_pos == ["NOUN"]
                or (
                    len(tokens) <= 2 and head_pos == "NOUN" and content_token_count <= 1
                )
            ):
                is_weak_bare_noun = True
        elif generic and content_token_count <= 1:
            is_weak_bare_noun = True

    features = PhraseFeatures(
        surfaces=surfaces,
        lemmas=lemmas,
        pos_tags=pos_tags,
        token_count=len(tokens),
        content_token_count=content_token_count,
        stopword_ratio=stopword_ratio,
        content_token_ratio=content_token_ratio,
        head_lemma=head_lemma,
        head_pos=head_pos,
        has_entity=has_entity,
        has_propn=has_propn,
        noun_headed=(
            bool(noun_headed and head_pos in {"NOUN", "PROPN"})
            if annotations_complete
            else bool(content_token_count > 0 and not verb_headed)
        ),
        verb_headed=verb_headed,
        is_weak_bare_noun=is_weak_bare_noun,
        annotations_complete=annotations_complete,
        language=lang,
        canonical_key=canonical,
        display_form=display_form,
    )

    # --- Hard rejects ---
    if all(_token_is_stop(tok, stopwords) for tok in tokens):
        return PhraseQualityResult(False, REASON_ALL_STOPWORDS, (), features)

    # Full-phrase tic/discourse mask hit (multi-word entries + unigrams in mask).
    if display_form in mask or canonical in mask:
        return PhraseQualityResult(False, TIC_OR_DISCOURSE_MASK, (), features)
    if any(tok.surface in mask or tok.lemma in mask for tok in tokens):
        # Only reject when a token itself is masked (existing behaviour for hedges/tics).
        return PhraseQualityResult(False, TIC_OR_DISCOURSE_MASK, (), features)

    if english:
        if exact_phrase_match(res.discourse_formulas, tokens):
            return PhraseQualityResult(False, DISCOURSE_FORMULA, (), features)
        if _is_prep_discourse_noun(tokens, res):
            return PhraseQualityResult(False, DISCOURSE_FORMULA, (), features)
        if _is_light_verb_construction(tokens, res):
            return PhraseQualityResult(False, LIGHT_VERB_CONSTRUCTION, (), features)

    if _is_pronoun_shard(
        tokens, stopwords=stopwords, annotations_complete=annotations_complete
    ):
        return PhraseQualityResult(False, PRONOUN_SHARD, (), features)

    if content_token_count <= 0:
        return PhraseQualityResult(False, NO_CONTENT_TOKEN, (), features)

    if _is_short_token_shard(tokens):
        return PhraseQualityResult(False, SHORT_TOKEN_SHARD, (), features)

    # --- Soft penalties ---
    penalties: list[str] = []
    if is_weak_bare_noun:
        penalties.append(WEAK_BARE_NOUN)
    if content_token_ratio < 0.5:
        penalties.append(LOW_CONTENT_RATIO)
    if 0.5 < stopword_ratio <= 0.7:
        penalties.append(BORDERLINE_STOPWORD_RATIO)
    if stopword_ratio > 0.7:
        # High stopword with some content: soft unless already hard-rejected.
        penalties.append(BORDERLINE_STOPWORD_RATIO)
    if english and head_lemma in res.light_verbs and head_pos == "VERB":
        penalties.append(LIGHT_VERB_HEAD)
    if distinctiveness is not None and distinctiveness < 0.05:
        penalties.append(LOW_DISTINCTIVENESS)

    return PhraseQualityResult(
        accepted_for_scoring=True,
        hard_reject_reason=None,
        penalties=tuple(penalties),
        features=features,
    )
