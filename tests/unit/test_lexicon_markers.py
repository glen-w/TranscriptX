"""Unit tests for shared lexicon marker matcher."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.lexicon_markers import (
    MarkerHit,
    MarkerPhrase,
    aggregate_rates,
    derive_epistemic_shares,
    derive_soft_request_ratio,
    is_english_supported,
    load_package_lexicon,
    match_phrases_in_text,
    resolve_transcript_language,
    tokenize,
)


@pytest.mark.unit
def test_longest_match_wins() -> None:
    phrases = [
        MarkerPhrase("kind of", "approximator", 2),
        MarkerPhrase("kind", "approximator", 1),
    ]
    hits = match_phrases_in_text(
        "It was kind of odd",
        phrases,
        speaker="A",
        segment_index=0,
        module="epistemic_markers",
    )
    assert len(hits) == 1
    assert hits[0].surface.casefold() == "kind of"


@pytest.mark.unit
def test_non_overlapping_greedy() -> None:
    phrases = [
        MarkerPhrase("i think", "epistemic_hedge", 2),
        MarkerPhrase("think", "epistemic_hedge", 1),
    ]
    hits = match_phrases_in_text(
        "I think I think so",
        phrases,
        speaker="A",
        segment_index=0,
        module="epistemic_markers",
    )
    assert len(hits) == 2
    assert all(h.surface.casefold() == "i think" for h in hits)


@pytest.mark.unit
def test_word_boundary_avoids_substring() -> None:
    phrases = [MarkerPhrase("may", "modal_uncertainty", 1)]
    hits = match_phrases_in_text(
        "maybe later",
        phrases,
        speaker="A",
        segment_index=0,
        module="epistemic_markers",
    )
    assert hits == []


@pytest.mark.unit
def test_package_lexicons_load_and_no_cross_module_modals() -> None:
    epi = load_package_lexicon("epistemic_markers_en.json")
    pol = load_package_lexicon("politeness_en.json")
    epi_surfaces = {p.surface for items in epi.values() for p in items}
    pol_surfaces = {p.surface for items in pol.values() for p in items}
    assert "could you" in pol_surfaces
    assert "would you" in pol_surfaces
    assert "could you" not in epi_surfaces
    assert "maybe" in epi_surfaces
    assert "maybe" not in pol_surfaces


@pytest.mark.unit
def test_language_gate() -> None:
    code, tag = resolve_transcript_language(
        [{"text": "hola", "language": "es"}], metadata={}
    )
    assert code == "es"
    assert tag == "segment_language"
    assert not is_english_supported(code)
    code2, tag2 = resolve_transcript_language([{"text": "hi"}], metadata={})
    assert code2 == "en"
    assert tag2 == "assumed_en_missing_metadata"
    assert is_english_supported(code2)


@pytest.mark.unit
def test_aggregate_rates_and_derived() -> None:
    hits = [
        MarkerHit("A", 0, 0, 7, "I think", "epistemic_hedge", "epistemic_markers"),
        MarkerHit(
            "A", 0, 10, 19, "definitely", "certainty_booster", "epistemic_markers"
        ),
    ]
    categories = [
        "epistemic_hedge",
        "approximator",
        "modal_uncertainty",
        "certainty_booster",
    ]
    global_stats, speaker_stats = aggregate_rates(
        hits, {"A": 20}, categories, min_tokens_for_rates=5
    )
    assert global_stats["total_marker_hits"] == 2
    assert speaker_stats["A"]["category_counts"]["epistemic_hedge"] == 1
    shares = derive_epistemic_shares(global_stats)
    assert shares["hedge_share"] == 0.5
    assert shares["booster_share"] == 0.5


@pytest.mark.unit
def test_soft_request_ratio() -> None:
    stats = {
        "category_counts": {
            "request_softener": 3,
            "bare_directive": 1,
        }
    }
    assert derive_soft_request_ratio(stats) == 0.75
    assert derive_soft_request_ratio({"category_counts": {}}) is None


@pytest.mark.unit
def test_tokenize_drops_short() -> None:
    assert "a" not in tokenize("a bit odd")
    assert "bit" in tokenize("a bit odd")
