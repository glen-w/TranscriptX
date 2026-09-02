"""Insights GUI: highlight card collection, filters, chrome, and jump wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit
from transcriptx.web.insights_presentation import (
    GUIDED_HIGHLIGHT_CARD_CAP,
    GUIDED_RANKED_ROW_CAP,
    analysis_group_headings,
    dedupe_overlapping_highlights,
    highlight_quote_eligible,
)


@pytest.mark.unit
def test_collect_highlight_cards_dedupes_section_vs_quotes() -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    highlights = {
        "transcript_key": "mini",
        "themes": [
            {
                "label": "Launch plan",
                "quote_ids": [],  # filled after we know stable ids — set below
                "conflict_event_ids": [],
            }
        ],
        "sections": {
            "cold_open": {
                "items": [
                    {
                        "speaker": "Alice",
                        "quote": "We should move the launch date carefully forward now.",
                        "start": 1.0,
                        "end": 4.0,
                        "segment_refs": {"segment_indexes": [0]},
                        "score": {"total": 0.91, "breakdown": {"w": 1}},
                    },
                    {
                        "speaker": "Bob",
                        "quote": "Completely different catering discussion for Friday.",
                        "start": 40.0,
                        "end": 45.0,
                        "segment_refs": {"segment_indexes": [3]},
                        "score": {"total": 0.7, "breakdown": {}},
                    },
                ]
            },
            "conflict_points": {"events": []},
        },
    }
    from transcriptx.core.analysis.highlights.post_process import (
        collect_highlight_quotes,
        stable_quote_id,
    )

    quotes = collect_highlight_quotes(highlights)
    assert quotes
    qid0 = stable_quote_id(quotes[0], "mini")
    highlights["themes"][0]["quote_ids"] = [qid0]

    cards = ib._collect_highlight_cards(highlights)
    quotes_text = [c.quote for c in cards]
    # First quote appears once (theme+section flatten must not duplicate)
    assert (
        quotes_text.count("We should move the launch date carefully forward now.") == 1
    )
    themed = [
        c
        for c in cards
        if c.quote == "We should move the launch date carefully forward now."
    ]
    assert themed[0].theme_label == "Launch plan"
    assert any("catering" in c.quote for c in cards)


@pytest.mark.unit
def test_collect_highlight_cards_maps_unthemed_label() -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    highlights = {
        "transcript_key": "mini",
        "themes": [
            {
                "label": "Unthemed",
                "is_unthemed": True,
                "quote_ids": [],
                "conflict_event_ids": [],
            }
        ],
        "sections": {
            "cold_open": {
                "items": [
                    {
                        "speaker": "Alice",
                        "quote": "A long enough excerpt that Guided eligibility will accept it.",
                        "start": 1.0,
                        "end": 3.0,
                        "segment_refs": {"segment_indexes": [0]},
                        "score": {"total": 0.8, "breakdown": {}},
                    }
                ]
            }
        },
    }
    from transcriptx.core.analysis.highlights.post_process import (
        collect_highlight_quotes,
        stable_quote_id,
    )

    quotes = collect_highlight_quotes(highlights)
    qid = stable_quote_id(quotes[0], "mini")
    highlights["themes"][0]["quote_ids"] = [qid]
    cards = ib._collect_highlight_cards(highlights)
    assert cards
    assert cards[0].theme_label == "Other highlights"


@pytest.mark.unit
def test_highlights_filters_apply_before_guided_cap(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib
    from transcriptx.web.insights_presentation import HighlightCardModel

    DummyHomeStreamlit.session_state = {
        "insights_detail_mode": "guided",
        "highlights_section_filter": "peak_moments",
        "highlights_speaker_filter": [],
        "highlights_min_score": 0.0,
    }
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(DummyHomeStreamlit, "expander", lambda *a, **k: _Exp())
    monkeypatch.setattr(DummyHomeStreamlit, "container", lambda **k: _Exp())
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_full", lambda: False
    )
    monkeypatch.setattr(ib, "load_accent_resolve_context", lambda: None)
    monkeypatch.setattr(ib, "speaker_inline_html", lambda *a, **k: "Alice")
    monkeypatch.setattr(ib, "_render_open_in_transcript_button", lambda **k: None)

    shown_sections: list[str] = []

    def capture_card(card, **k):
        shown_sections.append(card.section)

    monkeypatch.setattr(ib, "_render_highlight_card", capture_card)

    cards = [
        HighlightCardModel(
            event_key="a",
            theme_label="Cold open",
            speakers=("Alice",),
            start=0.0,
            end=2.0,
            quote="Eligible cold open excerpt that is long enough here.",
            section="cold_open",
            score=0.95,
            breakdown={},
            segment_index=0,
        ),
        HighlightCardModel(
            event_key="b",
            theme_label="Peak",
            speakers=("Alice",),
            start=10.0,
            end=12.0,
            quote="Eligible peak moment excerpt that is long enough here.",
            section="peak_moments",
            score=0.9,
            breakdown={},
            segment_index=1,
        ),
    ]
    monkeypatch.setattr(ib, "_collect_highlight_cards", lambda *_a, **_k: cards)
    fn = getattr(
        ib._highlights_browser_fragment, "__wrapped__", ib._highlights_browser_fragment
    )
    fn({"sections": {}}, session_slug="s", run_id="r", audio_available=False)
    assert shown_sections == ["peak_moments"]


class _Exp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.mark.unit
def test_insights_section_nav_persists_selection(monkeypatch) -> None:
    import transcriptx.web.page_modules.insights as page

    DummyHomeStreamlit.session_state = {"insights_section": "highlights"}
    monkeypatch.setattr(page, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit,
        "segmented_control",
        classmethod(
            lambda cls, _label, options, *, key=None, default=None, **k: "Highlights"
        ),
    )
    assert page._render_section_nav() == "highlights"
    assert DummyHomeStreamlit.session_state["insights_section"] == "highlights"


@pytest.mark.unit
def test_analysis_group_headings_stable_order() -> None:
    placements = [
        SimpleNamespace(block_id="insights_contract"),
        SimpleNamespace(block_id="keyphrases_block"),
        SimpleNamespace(block_id="lexical_diversity_block"),
        SimpleNamespace(block_id="politeness_block"),
    ]
    groups = analysis_group_headings(placements)
    titles = [t for _k, t, _ps in groups]
    assert titles == [
        "Language profile",
        "Interaction style",
        "Topics and salience",
    ]
    topics = next(ps for _k, t, ps in groups if t == "Topics and salience")
    assert [p.block_id for p in topics] == ["keyphrases_block", "insights_contract"]


@pytest.mark.unit
def test_keyphrases_guided_lists_five_not_dataframe(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {}
    writes: list[str] = []
    dfs: list = []
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit, "write", lambda text, *a, **k: writes.append(str(text))
    )
    monkeypatch.setattr(
        DummyHomeStreamlit, "dataframe", lambda *a, **k: dfs.append(True)
    )
    monkeypatch.setattr(DummyHomeStreamlit, "expander", lambda *a, **k: _Exp())
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    phrases = [
        {"rank": i, "phrase": f"phrase number {i}", "rank_weight": 1.0 - i * 0.05}
        for i in range(12)
    ]
    ib._render_keyphrases_payload(
        {
            "usable": True,
            "methods_run": ["noun_chunks"],
            "global_by_method": {"noun_chunks": {"phrases": phrases}},
        }
    )
    assert len([w for w in writes if w.startswith("- ")]) == GUIDED_RANKED_ROW_CAP
    assert dfs  # details expander still renders full table


@pytest.mark.unit
def test_marker_guided_hides_category_table_until_details(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {}
    dfs: list = []
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit, "dataframe", lambda *a, **k: dfs.append(True)
    )
    monkeypatch.setattr(DummyHomeStreamlit, "expander", lambda *a, **k: _Exp())
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    ib._render_marker_module_payload(
        {
            "usable": True,
            "global_stats": {
                "hits_per_100_tokens": 2.5,
                "hedge_share": 0.6,
                "booster_share": 0.2,
                "category_counts": {"hedge": 3, "booster": 1},
            },
            "speaker_stats": {
                "Alice": {"hits_per_100_tokens": 3.0, "token_count": 100}
            },
            "hits": [{"speaker": "Alice", "category": "hedge", "surface": "maybe"}],
        },
        share_keys=("hedge_share", "booster_share"),
        module="epistemic_markers",
    )
    # Guided still opens Explore details (dataframes live there)
    assert dfs


@pytest.mark.unit
def test_guided_highlight_cap_constant() -> None:
    assert GUIDED_HIGHLIGHT_CARD_CAP == 5
    assert highlight_quote_eligible("x" * 30)
    kept = dedupe_overlapping_highlights([])
    assert kept == []


@pytest.mark.unit
def test_navigate_highlight_to_transcript_sets_nav(monkeypatch) -> None:
    from transcriptx.web import navigation as nav
    from transcriptx.web.state import NAV_REQUEST_KEY, PAGE_KEY

    state: dict = {}
    called = {"n": 0}

    class _St:
        session_state = state

        @staticmethod
        def rerun():
            called["n"] += 1

    import transcriptx.web.transcript_navigation as transcript_nav

    monkeypatch.setattr(transcript_nav, "st", _St)

    nav.navigate_highlight_to_transcript(
        session_slug="sess",
        run_id="run1",
        segment_index=4,
        start_time=12.5,
        highlight_query="needle phrase",
    )
    assert state[PAGE_KEY] == "Transcript"
    assert state[NAV_REQUEST_KEY].segment_ref.segment_index == 4
    assert state[NAV_REQUEST_KEY].highlight_query == "needle phrase"
    assert called["n"] == 1


@pytest.mark.unit
def test_highlight_html_empty_and_none_query() -> None:
    from transcriptx.web.transcript_viewer.highlight import render_highlight_html

    assert render_highlight_html("", "x") == ""
    assert render_highlight_html("Hello", None) == "Hello"
    assert render_highlight_html("Hello", "  ") == "Hello"
    assert "<mark>Hel</mark>" in render_highlight_html("Hello", "Hel")


@pytest.mark.unit
def test_insights_chrome_is_section_nav_only(monkeypatch) -> None:
    import transcriptx.web.page_modules.insights as page

    DummyHomeStreamlit.session_state = {"insights_section": "summary"}
    monkeypatch.setattr(page, "st", DummyHomeStreamlit)
    monkeypatch.setattr(page, "_render_section_nav", lambda: "summary")
    assert page._render_chrome() == "summary"
    assert not hasattr(page, "render_insights_detail_mode_control")


@pytest.mark.unit
def test_insights_detail_mode_is_always_full() -> None:
    from transcriptx.web.insights_presentation import (
        get_insights_detail_mode,
        is_insights_full,
        is_insights_guided,
    )

    assert get_insights_detail_mode() == "full"
    assert is_insights_full() is True
    assert is_insights_guided() is False
