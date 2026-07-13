"""Tests for shared phrase quality analyser, resources, and policies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.phrase_quality.analyser import (
    analyse_phrase,
    annotations_from_surfaces,
)
from transcriptx.core.analysis.phrase_quality.policies import (
    content_phrase_policy,
    highlight_label_policy,
    theme_label_policy,
)
from transcriptx.core.analysis.phrase_quality.resources import (
    load_theme_phrase_resources,
    normalize_phrase_text,
    reset_theme_phrase_resources_cache,
    validate_theme_phrase_payload,
)
from transcriptx.core.analysis.phrase_quality.scoring import (
    adjust_theme_score,
    select_diverse_themes,
    theme_sort_key,
)
from transcriptx.core.analysis.phrase_quality.types import (
    DISCOURSE_FORMULA,
    LIGHT_VERB_CONSTRUCTION,
    WEAK_BARE_NOUN,
)
from transcriptx.core.utils.nlp_utils import build_tic_mask


def _anns(text: str, *, pos: list[str] | None = None):
    surfaces = text.split()
    return annotations_from_surfaces(surfaces, pos_tags=pos, lemmas=surfaces)


def test_hard_rejects_discourse_formulas_and_light_verbs() -> None:
    cases = {
        "of course": DISCOURSE_FORMULA,
        "for example": DISCOURSE_FORMULA,
        "need to": LIGHT_VERB_CONSTRUCTION,
        "going to": LIGHT_VERB_CONSTRUCTION,
        "we need": LIGHT_VERB_CONSTRUCTION,
    }
    for phrase, reason in cases.items():
        result = analyse_phrase(_anns(phrase))
        assert result.accepted_for_scoring is False, phrase
        assert result.hard_reject_reason == reason, phrase
        assert theme_label_policy(result).include is False
        assert content_phrase_policy(result).include is False
        assert highlight_label_policy(result).include is False


def test_soft_penalty_weak_bare_noun_the_war() -> None:
    result = analyse_phrase(_anns("the war", pos=["DET", "NOUN"]))
    assert result.accepted_for_scoring is True
    assert WEAK_BARE_NOUN in result.penalties
    # Still includable under highlight / theme (demoted), not hard-rejected.
    assert highlight_label_policy(result).include is True
    assert theme_label_policy(result).include is True
    assert theme_label_policy(result).rank_penalty > 0


def test_false_positive_keeps() -> None:
    keep = [
        ("need assessment", ["NOUN", "NOUN"]),
        ("course design", ["NOUN", "NOUN"]),
        ("example dataset", ["NOUN", "NOUN"]),
        ("going concern", ["VERB", "NOUN"]),
        ("war crimes investigation", ["NOUN", "NOUN", "NOUN"]),
        ("point estimate", ["NOUN", "NOUN"]),
        ("budget risk", ["NOUN", "NOUN"]),
        ("next step", ["ADJ", "NOUN"]),
        ("delay launch", ["VERB", "NOUN"]),
    ]
    for phrase, pos in keep:
        result = analyse_phrase(_anns(phrase, pos=pos))
        assert result.accepted_for_scoring is True, phrase
        assert result.hard_reject_reason is None, phrase


def test_substring_tokens_from_formulas_are_not_banned() -> None:
    # "course" alone must not inherit a ban from "of course".
    result = analyse_phrase(_anns("course design", pos=["NOUN", "NOUN"]))
    assert result.accepted_for_scoring is True
    assert result.hard_reject_reason != DISCOURSE_FORMULA


def test_discourse_formulas_not_auto_merged_into_global_tic_mask() -> None:
    mask = build_tic_mask()
    # Theme-only formulas introduced by this work must not widen the global mask.
    for formula in ("of course", "for example", "need to", "going to", "we need"):
        assert formula not in mask
    resources = load_theme_phrase_resources()
    assert ("of", "course") in resources.discourse_formulas
    assert "need" in resources.light_verbs


def test_resource_schema_validation(tmp_path: Path) -> None:
    reset_theme_phrase_resources_cache()
    good = {
        "discourse_formulas": ["of course", "of course", "For Example"],
        "light_verbs": ["need", "NEED", "want"],
        "pronoun_subjects": ["we", "i"],
        "discourse_nouns": ["course", "example"],
    }
    normalized = validate_theme_phrase_payload(good)
    assert ("of", "course") in [tuple(x) for x in normalized["discourse_formulas"]]
    assert normalized["light_verbs"].count("need") == 1

    with pytest.raises(ValueError, match="missing required"):
        validate_theme_phrase_payload({"discourse_formulas": []})

    with pytest.raises(ValueError, match="must be a list"):
        validate_theme_phrase_payload(
            {
                "discourse_formulas": "bad",
                "light_verbs": [],
                "pronoun_subjects": [],
                "discourse_nouns": [],
            }
        )

    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps({"discourse_formulas": [1]}), encoding="utf-8")
    resources = load_theme_phrase_resources(bad_path)
    assert resources.fingerprint == "invalid"
    reset_theme_phrase_resources_cache()


def test_score_formula_and_tie_break_stable() -> None:
    a = analyse_phrase(_anns("budget risk", pos=["NOUN", "NOUN"]))
    b = analyse_phrase(_anns("budget risk", pos=["NOUN", "NOUN"]))
    assert adjust_theme_score(1.0, a, source="noun_chunk") == adjust_theme_score(
        1.0, b, source="noun_chunk"
    )
    key_a = theme_sort_key(1.5, a, preference_tier=0)
    key_b = theme_sort_key(1.5, b, preference_tier=0)
    assert key_a == key_b


def test_diverse_theme_filling_dedupes_near_duplicates() -> None:
    cands = [
        {
            "phrase": "war in ukraine",
            "canonical_key": "war in ukraine",
            "tokens": ["war", "in", "ukraine"],
            "head_lemma": "war",
        },
        {
            "phrase": "the war in ukraine",
            "canonical_key": "war in ukraine",
            "tokens": ["the", "war", "in", "ukraine"],
            "head_lemma": "war",
        },
        {
            "phrase": "budget risk",
            "canonical_key": "budget risk",
            "tokens": ["budget", "risk"],
            "head_lemma": "risk",
        },
    ]
    selected = select_diverse_themes(cands, limit=3)
    texts = {row["phrase"] for row in selected}
    assert "budget risk" in texts
    assert len(selected) == 2


def test_normalize_phrase_text_strips_punctuation() -> None:
    assert normalize_phrase_text("Of Course!") == "of course"
    assert normalize_phrase_text("  need-to  ") == "need to"


def test_non_english_skips_english_structural_rules() -> None:
    # Without English rules, "of course" is only rejected if stopword/mask based.
    # With POS content, non-English path should not apply DISCOURSE_FORMULA.
    result = analyse_phrase(
        _anns("of course", pos=["ADP", "NOUN"]),
        language="fr",
    )
    # May still be weak / low content, but not English DISCOURSE_FORMULA.
    assert result.hard_reject_reason != DISCOURSE_FORMULA
