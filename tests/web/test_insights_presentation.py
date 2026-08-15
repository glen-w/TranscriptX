"""Unit tests for Insights presentation helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.insights_presentation import (
    GUIDED_HIGHLIGHT_CARD_CAP,
    GUIDED_RANKED_ROW_CAP,
    HighlightCardModel,
    SUMMARY_TYPE_LABELS,
    compact_metadata_chips,
    dedupe_overlapping_highlights,
    highlight_quote_eligible,
    order_analysis_placements,
    theme_label_for_user,
    truncate_for_preview,
)


@pytest.mark.unit
def test_summary_type_labels_cover_three_kinds() -> None:
    assert set(SUMMARY_TYPE_LABELS) == {
        "llm_summary",
        "narrative_summary",
        "executive_summary",
    }
    assert SUMMARY_TYPE_LABELS["llm_summary"] == "Transcript Summary"


@pytest.mark.unit
def test_compact_metadata_chips_cap() -> None:
    chips = compact_metadata_chips(
        ["A", "B", "C", "D", "E", "A"],
        cap=4,
    )
    assert chips == ["A", "B", "C", "D"]


@pytest.mark.unit
def test_truncate_for_preview_is_non_destructive() -> None:
    body = "Paragraph one.\n\n" + ("word " * 500)
    preview, truncated = truncate_for_preview(body, limit=80)
    assert truncated
    assert len(preview) <= len(body)
    assert body.startswith(preview[:20]) or preview in body


@pytest.mark.unit
def test_order_analysis_placements_groups_modules() -> None:
    class P:
        def __init__(self, block_id: str) -> None:
            self.block_id = block_id

    placements = [
        P("lexical_diversity_block"),
        P("politeness_block"),
        P("insights_contract"),
        P("keyphrases_block"),
        P("epistemic_markers_block"),
    ]
    ordered = order_analysis_placements(placements)
    assert [p.block_id for p in ordered] == [
        "lexical_diversity_block",
        "epistemic_markers_block",
        "politeness_block",
        "keyphrases_block",
        "insights_contract",
    ]


@pytest.mark.unit
def test_theme_label_unthemed_becomes_other() -> None:
    assert theme_label_for_user("Unthemed", is_unthemed=True) == "Other highlights"
    assert theme_label_for_user("Budget", is_unthemed=False) == "Budget"


@pytest.mark.unit
def test_analysis_payload_has_user_content_gates() -> None:
    from transcriptx.web.insights_presentation import analysis_payload_has_user_content

    assert not analysis_payload_has_user_content("insights", {})
    assert not analysis_payload_has_user_content(
        "insights", {"key_themes": [], "recurring_ideas": [], "style_markers": {}}
    )
    assert analysis_payload_has_user_content(
        "insights",
        {
            "key_themes": [{"phrase": "roadmap"}],
            "recurring_ideas": [],
            "style_markers": {},
        },
    )
    assert not analysis_payload_has_user_content(
        "keyphrases",
        {"usable": True, "global_by_method": {"noun_chunks": {"phrases": []}}},
    )
    assert analysis_payload_has_user_content(
        "keyphrases",
        {
            "usable": True,
            "global_by_method": {
                "noun_chunks": {"phrases": [{"phrase": "quarterly plan"}]}
            },
        },
    )
    assert not analysis_payload_has_user_content(
        "epistemic_markers",
        {"usable": False, "global_stats": {"hits_per_100_tokens": 1}},
    )


@pytest.mark.unit
def test_load_cached_analysis_json_loads_once(monkeypatch) -> None:
    from transcriptx.web import insights_presentation as ip

    class _SS(dict):
        pass

    class _St:
        session_state = _SS()

    monkeypatch.setattr(ip, "st", _St)
    ip.clear_analysis_payload_cache()
    calls = {"n": 0}

    class Loader:
        def load_json(self, module, suffix):
            calls["n"] += 1
            return {"global_stats": {"ttr": 0.1}}

    loader = Loader()
    a = ip.load_cached_analysis_json(
        loader, "lexical_diversity", "_lexical_diversity.json"
    )
    b = ip.load_cached_analysis_json(
        loader, "lexical_diversity", "_lexical_diversity.json"
    )
    assert a == b
    assert calls["n"] == 1


@pytest.mark.unit
def test_highlight_quote_eligibility() -> None:
    assert not highlight_quote_eligible("hi")
    assert not highlight_quote_eligible("{'a': 1}")
    assert highlight_quote_eligible(
        "This is a usable transcript excerpt for a highlight."
    )


@pytest.mark.unit
def test_dedupe_overlapping_highlights_keeps_stronger() -> None:
    a = HighlightCardModel(
        event_key="a",
        theme_label="T",
        speakers=("Alice",),
        start=10.0,
        end=20.0,
        quote="we should move the launch date carefully forward",
        section="cold_open",
        score=0.9,
        breakdown=None,
        segment_index=0,
    )
    b = HighlightCardModel(
        event_key="b",
        theme_label="T",
        speakers=("Alice",),
        start=11.0,
        end=19.0,
        quote="we should move the launch date carefully forward now",
        section="cold_open",
        score=0.5,
        breakdown=None,
        segment_index=1,
    )
    c = HighlightCardModel(
        event_key="c",
        theme_label="Other",
        speakers=("Bob",),
        start=40.0,
        end=50.0,
        quote="completely different discussion about catering",
        section="peak_moments",
        score=0.7,
        breakdown=None,
        segment_index=2,
    )
    kept = dedupe_overlapping_highlights([a, b, c])
    keys = {k.event_key for k in kept}
    assert "a" in keys
    assert "b" not in keys
    assert "c" in keys
    assert GUIDED_HIGHLIGHT_CARD_CAP == 5
    assert GUIDED_RANKED_ROW_CAP == 5
