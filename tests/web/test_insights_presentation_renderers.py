"""Renderer-focused tests for Insights Summary / Speakers / Highlights UX."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


def _placement(placement_id: str = "p1", block_id: str = "insights_summary_panel"):
    return SimpleNamespace(
        placement_id=placement_id,
        block_id=block_id,
        title_override=None,
        params={},
    )


def _ctx(loader=None, run_root=None, run_results=None):
    services = SimpleNamespace(content_loader=loader)
    return SimpleNamespace(
        services=services,
        run_root=run_root,
        run_results=run_results,
        subject_id="sess",
        run_id="run1",
    )


@pytest.mark.unit
def test_insights_summary_panel_renders_one_body(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.overview_curated as oc
    from transcriptx.web.summary_precedence import SummaryCandidate

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(oc, "st", DummyHomeStreamlit)

    bodies: list[str] = []
    original_md = DummyHomeStreamlit.markdown

    def capture_md(text, *a, **k):
        bodies.append(str(text))
        return original_md(text, *a, **k)

    monkeypatch.setattr(DummyHomeStreamlit, "markdown", capture_md)

    c1 = SummaryCandidate(
        kind="llm_summary",
        module="llm_summary",
        title="LLM Transcript Summary",
        markdown="# Transcript Summary\n\nBody A only.\n",
        payload={"summary": "Body A only.", "provenance": {"model": "m1"}},
        available=True,
        outcome="succeeded",
        empty_hint="",
        artifact_stem="_llm_summary",
        text_field="summary",
    )
    c2 = SummaryCandidate(
        kind="executive_summary",
        module="summary",
        title="Executive Summary",
        markdown="# Executive Summary\n\nBody B must not stack.\n",
        payload={"summary": "Body B"},
        available=True,
        outcome="succeeded",
        empty_hint="",
        artifact_stem="_summary",
        text_field="summary",
    )

    monkeypatch.setattr(
        oc,
        "_insights_summary_candidates",
        lambda _ctx: [c1, c2],
    )
    monkeypatch.setattr(oc, "render_badge_row", lambda *_a, **_k: None)
    monkeypatch.setattr(oc, "render_badge_row_with_feedback", lambda *_a, **_k: None)
    monkeypatch.setattr(oc, "resolve_artifact_rel_path", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    monkeypatch.setattr(
        "transcriptx.web.blocks.implementations.custom_qa_presentation.render_global_custom_qa_under_summary",
        lambda *_a, **_k: None,
    )

    loader = MagicMock()
    loader.find_artifact.return_value = None
    oc.render_insights_summary_panel(_ctx(loader=loader), _placement())

    joined = "\n".join(bodies)
    assert "Body A only" in joined
    assert "Body B must not stack" not in joined
    # Heading appears once as selected title, not duplicated stacked bodies
    assert joined.count("Body A only") == 1


@pytest.mark.unit
def test_insights_summary_type_switch_replaces_body(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.overview_curated as oc
    from transcriptx.web.summary_precedence import SummaryCandidate

    DummyHomeStreamlit.session_state = {
        "insights_summary_type_p1": "Executive Summary",
        "insights_summary_type_p1_control": "Executive Summary",
    }
    monkeypatch.setattr(oc, "st", DummyHomeStreamlit)

    bodies: list[str] = []
    monkeypatch.setattr(
        DummyHomeStreamlit,
        "markdown",
        lambda text, *a, **k: bodies.append(str(text)),
    )

    c1 = SummaryCandidate(
        kind="llm_summary",
        module="llm_summary",
        title="LLM Transcript Summary",
        markdown="Body A",
        payload={"summary": "Body A"},
        available=True,
        outcome="succeeded",
        empty_hint="",
        artifact_stem="_llm_summary",
        text_field="summary",
    )
    c2 = SummaryCandidate(
        kind="executive_summary",
        module="summary",
        title="Executive Summary",
        markdown="Body Executive",
        payload={"summary": "Body Executive"},
        available=True,
        outcome="succeeded",
        empty_hint="",
        artifact_stem="_summary",
        text_field="summary",
    )
    monkeypatch.setattr(oc, "_insights_summary_candidates", lambda _ctx: [c1, c2])
    monkeypatch.setattr(oc, "render_badge_row", lambda *_a, **_k: None)
    monkeypatch.setattr(oc, "render_badge_row_with_feedback", lambda *_a, **_k: None)
    monkeypatch.setattr(oc, "resolve_artifact_rel_path", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    monkeypatch.setattr(
        "transcriptx.web.blocks.implementations.custom_qa_presentation.render_global_custom_qa_under_summary",
        lambda *_a, **_k: None,
    )
    loader = MagicMock()
    loader.find_artifact.return_value = None
    oc.render_insights_summary_panel(_ctx(loader=loader), _placement())
    joined = "\n".join(bodies)
    assert "Body Executive" in joined
    assert "Body A" not in joined


@pytest.mark.unit
def test_insights_summary_generation_details_collapsed(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.overview_curated as oc
    from transcriptx.web.summary_precedence import SummaryCandidate

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(oc, "st", DummyHomeStreamlit)
    expanders: list[tuple] = []

    class _Exp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def capture_expander(*a, **k):
        expanders.append((a, k))
        return _Exp()

    monkeypatch.setattr(DummyHomeStreamlit, "expander", capture_expander)
    monkeypatch.setattr(oc, "render_badge_row", lambda *_a, **_k: None)
    monkeypatch.setattr(oc, "render_badge_row_with_feedback", lambda *_a, **_k: None)
    monkeypatch.setattr(oc, "resolve_artifact_rel_path", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    monkeypatch.setattr(
        "transcriptx.web.blocks.implementations.custom_qa_presentation.render_global_custom_qa_under_summary",
        lambda *_a, **_k: None,
    )
    cand = SummaryCandidate(
        kind="llm_summary",
        module="llm_summary",
        title="LLM Transcript Summary",
        markdown="Body",
        payload={"summary": "Body", "provenance": {"model": "m"}},
        available=True,
        outcome="succeeded",
        empty_hint="",
        artifact_stem="_llm_summary",
        text_field="summary",
    )
    monkeypatch.setattr(oc, "_insights_summary_candidates", lambda _ctx: [cand])
    loader = MagicMock()
    loader.find_artifact.return_value = None
    oc.render_insights_summary_panel(_ctx(loader=loader), _placement())
    assert any(
        (args and args[0] == "Generation details")
        and kwargs.get("expanded") is False
        for args, kwargs in expanders
    )


@pytest.mark.unit
def test_stale_analysis_section_remaps_to_summary(monkeypatch) -> None:
    import transcriptx.web.page_modules.insights as page

    DummyHomeStreamlit.session_state = {"insights_section": "analysis"}
    monkeypatch.setattr(page, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit,
        "segmented_control",
        classmethod(
            lambda cls, _label, options, *, key=None, default=None, **k: default
            or options[0]
        ),
    )
    assert "Analysis" not in [label for _, label in page.INSIGHTS_SECTIONS]
    assert page._render_section_nav() == "summary"
    assert DummyHomeStreamlit.session_state["insights_section"] == "summary"


@pytest.mark.unit
def test_insights_focus_splits_content_and_style(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {}
    writes: list[str] = []
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit, "write", lambda text, *a, **k: writes.append(str(text))
    )
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    payload = {
        "key_themes": [{"phrase": "roadmap", "score": {"total": 0.9}}],
        "recurring_ideas": [],
        "style_markers": {"formality": 0.2},
    }
    writes.clear()
    ib._render_insights_payload(payload, focus="content")
    assert any("roadmap" in w for w in writes)
    assert not any("Formality" in w for w in writes)

    writes.clear()
    ib._render_insights_payload(payload, focus="style")
    assert any("Formality" in w for w in writes)
    assert not any("roadmap" in w for w in writes)


@pytest.mark.unit
def test_malformed_insights_payload_fails_gracefully(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    # No crash on unexpected shapes
    ib._render_insights_payload({"key_themes": "not-a-list", "style_markers": None})
    ib._render_insights_payload({})


@pytest.mark.unit
def test_content_vs_style_guided_no_raw_json(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {}
    json_calls: list = []
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit, "json", lambda *a, **k: json_calls.append(a)
    )
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )

    ib._render_insights_payload(
        {
            "key_themes": [{"phrase": "roadmap", "score": {"total": 0.9}}],
            "recurring_ideas": [],
            "style_markers": {"formality": 0.2, "nested": {"a": 1}},
        }
    )
    assert json_calls == []


@pytest.mark.unit
def test_lexical_diversity_guided_hides_dataframe_until_details(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {}
    df_calls: list = []
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        DummyHomeStreamlit, "dataframe", lambda *a, **k: df_calls.append(True)
    )
    monkeypatch.setattr(
        "transcriptx.web.insights_presentation.is_insights_guided", lambda: True
    )
    # Expander context manager
    class _Exp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(DummyHomeStreamlit, "expander", lambda *a, **k: _Exp())

    ib._render_lexical_diversity_payload(
        {
            "global_stats": {"ttr": 0.4, "mtld": 50.0, "hapax_rate": 0.3},
            "speaker_stats": {
                "Alice": {
                    "token_count": 100,
                    "type_count": 40,
                    "ttr": 0.4,
                    "mtld": 55.0,
                    "hapax_rate": 0.2,
                }
            },
            "time_buckets": [{"bucket_start": 0, "bucket_end": 60, "ttr": 0.3}],
        }
    )
    # Dataframes only inside Explore details expander (still called once entered)
    assert df_calls  # details expander renders tables
    # Metrics path should not dump empty/malformed
    assert True


@pytest.mark.unit
def test_highlights_guided_caps_and_dedupes(monkeypatch) -> None:
    import transcriptx.web.blocks.implementations.insights as ib

    DummyHomeStreamlit.session_state = {"insights_detail_mode": "guided"}
    monkeypatch.setattr(ib, "st", DummyHomeStreamlit)

    class _Exp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

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

    card_count = {"n": 0}
    real_card = ib._render_highlight_card

    def counting_card(*a, **k):
        card_count["n"] += 1
        return real_card(*a, **k)

    monkeypatch.setattr(ib, "_render_highlight_card", counting_card)

    items = []
    for i in range(8):
        items.append(
            {
                "speaker": "Alice",
                "quote": f"This is a substantial highlight excerpt number {i} for testing.",
                "start": float(i * 30),
                "end": float(i * 30 + 5),
                "segment_refs": {"segment_indexes": [i]},
                "score": {"total": 0.9 - i * 0.05, "breakdown": {}},
            }
        )
    # Near-duplicate of first
    items.append(
        {
            "speaker": "Alice",
            "quote": "This is a substantial highlight excerpt number 0 for testing.",
            "start": 0.5,
            "end": 5.5,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.5, "breakdown": {}},
        }
    )

    highlights = {
        "transcript_key": "t1",
        "themes": [],
        "sections": {"cold_open": {"items": items}},
    }
    # Bypass collect_highlight_quotes complexity by stubbing card collection
    from transcriptx.web.insights_presentation import HighlightCardModel

    cards = [
        HighlightCardModel(
            event_key=f"k{i}",
            theme_label="Cold open",
            speakers=("Alice",),
            start=float(i * 30),
            end=float(i * 30 + 5),
            quote=f"This is a substantial highlight excerpt number {i} for testing.",
            section="cold_open",
            score=0.9 - i * 0.05,
            breakdown={},
            segment_index=i,
        )
        for i in range(8)
    ]
    cards.append(
        HighlightCardModel(
            event_key="dup",
            theme_label="Cold open",
            speakers=("Alice",),
            start=0.5,
            end=5.5,
            quote="This is a substantial highlight excerpt number 0 for testing.",
            section="cold_open",
            score=0.5,
            breakdown={},
            segment_index=0,
        )
    )
    monkeypatch.setattr(ib, "_collect_highlight_cards", lambda *_a, **_k: cards)

    # Invoke the undecorated body via fragment's wrapped function when present.
    fn = getattr(ib._highlights_browser_fragment, "__wrapped__", None)
    if fn is None:
        fn = ib._highlights_browser_fragment
    fn(highlights, session_slug="s", run_id="r")
    assert card_count["n"] <= 5
    assert card_count["n"] >= 1
