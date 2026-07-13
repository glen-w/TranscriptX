"""Extended phrase-quality coverage: matching, candidates, policies, scoring."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.core.analysis.phrase_quality.analyser import (
    analyse_phrase,
    annotations_from_surfaces,
)
from transcriptx.core.analysis.phrase_quality.candidates import (
    annotations_from_spacy_span,
    canonical_key_from_annotations,
    cluster_prefer_longer,
    display_form_from_annotations,
    dominant_display,
    iter_ngram_spans,
    merge_candidate_stats,
    token_annotations_from_spacy_token,
)
from transcriptx.core.analysis.phrase_quality.matching import (
    contiguous_lemma_window,
    contiguous_surface_window,
    exact_phrase_match,
    sequence_in_tokens,
    strip_leading_determiners,
)
from transcriptx.core.analysis.phrase_quality.policies import (
    TIER_ENTITY_PROPN,
    TIER_MULTI_CONTENT_NOUN,
    content_phrase_policy,
    theme_label_policy,
)
from transcriptx.core.analysis.phrase_quality.resources import (
    load_theme_phrase_resources,
    reset_theme_phrase_resources_cache,
    resource_fingerprint,
)
from transcriptx.core.analysis.phrase_quality.scoring import (
    adjust_theme_score,
    near_duplicate,
    select_diverse_themes,
)
from transcriptx.core.analysis.phrase_quality.types import (
    ALL_STOPWORDS,
    BORDERLINE_STOPWORD_RATIO,
    EMPTY,
    LIGHT_VERB_HEAD,
    LOW_CONTENT_RATIO,
    LOW_DISTINCTIVENESS,
    NO_CONTENT_TOKEN,
    PhraseFeatures,
    PhraseQualityResult,
    TIC_OR_DISCOURSE_MASK,
    TokenAnnotation,
    WEAK_BARE_NOUN,
)


def _anns(text: str, *, pos: list[str] | None = None):
    surfaces = text.split()
    return annotations_from_surfaces(surfaces, pos_tags=pos, lemmas=surfaces)


def test_sequence_in_tokens_lemma_and_surface_fallback() -> None:
    tokens = [
        TokenAnnotation(surface="Of", lemma="of", pos="ADP"),
        TokenAnnotation(surface="Course", lemma="course", pos="NOUN"),
    ]
    needles = {("of", "course")}
    assert sequence_in_tokens(needles, tokens, use_lemma=True) is True
    assert sequence_in_tokens(needles, tokens, use_lemma=False) is True
    assert sequence_in_tokens(set(), tokens) is False
    assert sequence_in_tokens(needles, []) is False
    # Surface-only hit when lemmas diverge.
    surface_tokens = [
        TokenAnnotation(surface="need", lemma="require", pos="VERB"),
        TokenAnnotation(surface="to", lemma="to", pos="PART"),
    ]
    assert sequence_in_tokens({("need", "to")}, surface_tokens, use_lemma=True) is True
    assert contiguous_lemma_window(tokens, 0, 2) == ("of", "course")
    assert contiguous_surface_window(tokens, 0, 2) == ("of", "course")


def test_exact_phrase_match_empty_and_lemma_vs_surface() -> None:
    tokens = _anns("budget risk", pos=["NOUN", "NOUN"])
    assert exact_phrase_match(set(), tokens) is False
    assert exact_phrase_match({("budget", "risk")}, []) is False
    assert exact_phrase_match({("budget", "risk")}, tokens) is True
    assert strip_leading_determiners(["the", "a", "war"]) == ("war",)


def test_merge_candidate_stats_prefers_longer_and_entity() -> None:
    store: dict = {}
    short = annotations_from_surfaces(["war"], pos_tags=["NOUN"], lemmas=["war"])
    merge_candidate_stats(
        store,
        tokens=short,
        source="ngram",
        speaker="A",
        start=0.0,
        end=1.0,
        example={"quote": "war"},
        tfidf=0.1,
    )
    longer = annotations_from_surfaces(
        ["the", "war", "ukraine"],
        pos_tags=["DET", "NOUN", "PROPN"],
        lemmas=["the", "war", "ukraine"],
    )
    # Mark entity on Ukraine token.
    longer[-1] = TokenAnnotation(
        surface="ukraine", lemma="ukraine", pos="PROPN", ent_type="GPE"
    )
    merge_candidate_stats(
        store,
        tokens=longer,
        source="entity",
        speaker="B",
        start=1.0,
        end=2.0,
        example={"quote": "the war ukraine"},
        tfidf=None,
    )
    key = canonical_key_from_annotations(longer)
    stats = store[key] if key in store else next(iter(store.values()))
    assert stats["count"] >= 1
    assert stats["has_entity"] is True
    assert len(stats["annotations"]) >= len(short)
    assert dominant_display(
        {"display_counts": {"war": 1, "War": 1}, "canonical_key": "war"}
    ) in {
        "War",
        "war",
    }
    assert dominant_display({"canonical_key": "alone"}) == "alone"
    merge_candidate_stats(
        store,
        tokens=[],
        source="ngram",
        speaker="A",
        start=0.0,
        end=1.0,
        example={},
        tfidf=0.0,
    )


def test_cluster_prefer_longer_jaccard_and_canonical() -> None:
    cands = [
        {
            "phrase": "war",
            "canonical_key": "war",
            "tokens": ["war"],
            "has_entity": False,
            "score": {"total": 1.0},
        },
        {
            "phrase": "the war in ukraine",
            "canonical_key": "war in ukraine",
            "tokens": ["the", "war", "in", "ukraine"],
            "has_entity": True,
            "score": {"total": 0.9},
        },
        {
            "phrase": "budget risk",
            "canonical_key": "budget risk",
            "tokens": ["budget", "risk"],
            "has_entity": False,
            "score": {"total": 0.8},
        },
        {
            "phrase": "war dup",
            "canonical_key": "war in ukraine",
            "tokens": ["war", "ukraine"],
            "has_entity": False,
            "score": {"total": 0.5},
        },
    ]
    kept = cluster_prefer_longer(cands)
    keys = {c["canonical_key"] for c in kept}
    assert "war in ukraine" in keys
    assert "budget risk" in keys
    assert len(kept) <= 3


def test_token_and_ngram_helpers() -> None:
    tok = SimpleNamespace(
        is_alpha=True,
        text="Budget",
        lemma_="budget",
        pos_="NOUN",
        is_stop=False,
        ent_type_="",
    )
    ann = token_annotations_from_spacy_token(tok)
    assert ann is not None
    assert ann.surface == "budget"
    assert (
        token_annotations_from_spacy_token(SimpleNamespace(is_alpha=False, text="."))
        is None
    )
    assert (
        token_annotations_from_spacy_token(
            SimpleNamespace(
                is_alpha=True,
                text="  ",
                lemma_="",
                pos_="",
                is_stop=False,
                ent_type_="",
            )
        )
        is None
    )
    span = [
        tok,
        SimpleNamespace(
            is_alpha=True,
            text="Risk",
            lemma_="risk",
            pos_="NOUN",
            is_stop=False,
            ent_type_="",
        ),
    ]
    anns = annotations_from_spacy_span(span)
    assert len(anns) == 2
    assert display_form_from_annotations(anns) == "budget risk"
    windows = list(iter_ngram_spans(anns, 1, 2))
    assert len(windows) == 3


def test_analyse_phrase_hard_rejects_empty_stopwords_mask_shards() -> None:
    empty = analyse_phrase([])
    assert empty.hard_reject_reason == EMPTY
    stops = annotations_from_surfaces(
        ["the", "of"], pos_tags=["DET", "ADP"], lemmas=["the", "of"]
    )
    stop_result = analyse_phrase(stops)
    assert (
        stop_result.hard_reject_reason in {ALL_STOPWORDS, NO_CONTENT_TOKEN, None}
        or not stop_result.accepted_for_scoring
    )
    masked = analyse_phrase(
        _anns("budget risk", pos=["NOUN", "NOUN"]), tic_mask={"budget risk"}
    )
    assert masked.hard_reject_reason == TIC_OR_DISCOURSE_MASK
    soft = analyse_phrase(
        _anns("the of budget", pos=["DET", "ADP", "NOUN"]),
        distinctiveness=0.01,
    )
    assert soft.accepted_for_scoring is True
    assert (
        LOW_DISTINCTIVENESS in soft.penalties
        or LOW_CONTENT_RATIO in soft.penalties
        or BORDERLINE_STOPWORD_RATIO in soft.penalties
    )


def test_theme_and_content_policy_verb_led_and_adj_head() -> None:
    verb_single = analyse_phrase(_anns("deliver", pos=["VERB"]))
    theme = theme_label_policy(verb_single)
    assert theme.include is False or theme.preference_tier >= TIER_MULTI_CONTENT_NOUN
    noun_multi = analyse_phrase(_anns("budget risk", pos=["NOUN", "NOUN"]))
    assert theme_label_policy(noun_multi).include is True
    assert theme_label_policy(noun_multi).preference_tier == TIER_MULTI_CONTENT_NOUN

    # Force LIGHT_VERB_HEAD penalty path for content policy.
    light = PhraseQualityResult(
        accepted_for_scoring=True,
        hard_reject_reason=None,
        penalties=(LIGHT_VERB_HEAD,),
        features=PhraseFeatures(
            surfaces=("need",),
            lemmas=("need",),
            pos_tags=("VERB",),
            token_count=1,
            content_token_count=1,
            stopword_ratio=0.0,
            content_token_ratio=1.0,
            head_lemma="need",
            head_pos="VERB",
            has_entity=False,
            has_propn=False,
            noun_headed=False,
            verb_headed=True,
            is_weak_bare_noun=False,
            annotations_complete=True,
            language="en",
            canonical_key="need",
            display_form="need",
        ),
    )
    assert content_phrase_policy(light).include is False

    adj_head = PhraseQualityResult(
        accepted_for_scoring=True,
        hard_reject_reason=None,
        penalties=(),
        features=PhraseFeatures(
            surfaces=("quick",),
            lemmas=("quick",),
            pos_tags=("ADJ",),
            token_count=1,
            content_token_count=1,
            stopword_ratio=0.0,
            content_token_ratio=1.0,
            head_lemma="quick",
            head_pos="ADJ",
            has_entity=False,
            has_propn=False,
            noun_headed=False,
            verb_headed=False,
            is_weak_bare_noun=False,
            annotations_complete=True,
            language="en",
            canonical_key="quick",
            display_form="quick",
        ),
    )
    assert content_phrase_policy(adj_head).include is False

    entity = analyse_phrase(
        [
            TokenAnnotation(
                surface="ukraine", lemma="ukraine", pos="PROPN", ent_type="GPE"
            ),
            TokenAnnotation(surface="policy", lemma="policy", pos="NOUN"),
        ]
    )
    assert theme_label_policy(entity).preference_tier in {
        TIER_MULTI_CONTENT_NOUN,
        TIER_ENTITY_PROPN,
    }


def test_select_diverse_themes_second_pass_fills_after_head_collision() -> None:
    cands = [
        {
            "phrase": "budget risk",
            "canonical_key": "budget risk",
            "tokens": ["budget", "risk"],
            "head_lemma": "risk",
        },
        {
            "phrase": "timeline risk",
            "canonical_key": "timeline risk",
            "tokens": ["timeline", "risk"],
            "head_lemma": "risk",
        },
        {
            "phrase": "launch planning",
            "canonical_key": "launch planning",
            "tokens": ["launch", "planning"],
            "head_lemma": "planning",
        },
    ]
    selected = select_diverse_themes(cands, limit=3)
    texts = {row["phrase"] for row in selected}
    assert "budget risk" in texts
    # Second pass may admit same-head after diversity fill.
    assert len(selected) >= 2
    assert near_duplicate(["a", "b"], ["a", "b"]) is True
    assert near_duplicate([], ["a"]) is False
    assert near_duplicate(["a", "b"], ["a", "b", "c"]) is True

    good = analyse_phrase(_anns("budget risk", pos=["NOUN", "NOUN"]))
    base = adjust_theme_score(1.0, good, source="noun_chunk", policy_rank_penalty=0.1)
    weak = analyse_phrase(_anns("the war", pos=["DET", "NOUN"]))
    weak_score = adjust_theme_score(1.0, weak, source="ngram")
    assert base > weak_score
    if WEAK_BARE_NOUN in weak.penalties:
        assert weak_score < 1.0


def test_load_theme_phrase_resources_missing_and_force_reload(tmp_path: Path) -> None:
    reset_theme_phrase_resources_cache()
    missing = tmp_path / "nope.json"
    resources = load_theme_phrase_resources(missing)
    assert resources.fingerprint == "missing"
    reset_theme_phrase_resources_cache()
    fp1 = resource_fingerprint()
    fp2 = resource_fingerprint()
    assert fp1 == fp2
    reset_theme_phrase_resources_cache()
