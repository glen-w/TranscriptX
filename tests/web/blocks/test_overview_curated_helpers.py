"""Unit tests for curated Overview badge helpers (0.3.6)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.web.blocks.implementations import overview_curated as oc


@pytest.mark.unit
def test_summary_source_badge_llm_vs_standard() -> None:
    assert oc._summary_source_badge("llm_summary") == "LLM"
    assert oc._summary_source_badge("narrative_summary") == "LLM"
    assert oc._summary_source_badge("executive_summary") == "Standard"


@pytest.mark.unit
def test_speaker_accent_color_cycles_distinct_palette() -> None:
    first = oc._speaker_accent_color(0)
    second = oc._speaker_accent_color(1)
    assert first != second
    assert first.startswith("#")
    assert oc._speaker_accent_color(len(oc._SPEAKER_ACCENTS)) == first
    # Name-stable accents match the shared helper used across the viewer.
    assert oc._speaker_accent_color("Alice") == oc._speaker_accent_color(" alice ")


@pytest.mark.unit
def test_summary_hero_badges_include_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oc,
        "provenance_badges",
        lambda prov: ["Ollama", "low"] if prov else [],
    )
    cand = SimpleNamespace(
        kind="llm_summary",
        payload={"provenance": {"provider": "ollama"}},
    )
    assert oc._summary_hero_badges(cand) == ["LLM", "Ollama", "low"]

    cand2 = SimpleNamespace(kind="executive_summary", payload={})
    assert oc._summary_hero_badges(cand2) == ["Standard"]


@pytest.mark.unit
def test_summary_hero_badges_include_named_analysis_preset() -> None:
    cand = SimpleNamespace(kind="llm_summary", payload={})
    assert oc._summary_hero_badges(
        cand, run_results={"analysis_preset": "balanced"}
    ) == ["Balanced", "LLM"]
    assert oc._summary_hero_badges(
        cand, run_results={"analysis_preset": "quick"}
    ) == ["Quick", "LLM"]
    assert oc._summary_hero_badges(
        cand, run_results={"analysis_preset": "thorough"}
    ) == ["Thorough", "LLM"]
    # Custom / missing → no preset badge
    assert oc._summary_hero_badges(
        cand, run_results={"analysis_preset": "custom"}
    ) == ["LLM"]
    assert oc._summary_hero_badges(cand, run_results={}) == ["LLM"]


@pytest.mark.unit
def test_render_summary_body_strips_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered: list[str] = []
    json_payloads: list[dict] = []

    class _St:
        @staticmethod
        def markdown(body):
            rendered.append(body)

        @staticmethod
        def json(payload):
            json_payloads.append(payload)

    monkeypatch.setattr(oc, "st", _St)
    monkeypatch.setattr(oc, "strip_commitments_section", lambda body: body + "|nocomm")
    monkeypatch.setattr(oc, "strip_leading_markdown_heading", lambda body: body[2:])
    monkeypatch.setattr(oc, "strip_provenance_footer", lambda body: body + "|noprov")

    cand = SimpleNamespace(
        markdown="# H\nBody",
        kind="executive_summary",
        payload={},
        text_field="summary",
    )
    oc._render_summary_body(cand, strip_heading=True, strip_provenance=True)
    assert rendered[-1].endswith("|noprov")
    assert "nocomm" in rendered[-1]

    rendered.clear()
    cand2 = SimpleNamespace(
        markdown="",
        kind="narrative_summary",
        payload={"summary": "plain text"},
        text_field="summary",
    )
    oc._render_summary_body(cand2)
    assert rendered == ["plain text"]

    cand3 = SimpleNamespace(
        markdown="",
        kind="executive_summary",
        payload={"summary": "", "commitments": {"items": []}, "x": 1},
        text_field="summary",
    )
    oc._render_summary_body(cand3)
    assert json_payloads[-1] == {"summary": "", "x": 1}
    assert "commitments" not in json_payloads[-1]


@pytest.mark.unit
def test_highlights_compact_skips_empty_unthemed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    infos: list[str] = []
    writes: list[str] = []

    class _St:
        @staticmethod
        def subheader(_title):
            return None

        @staticmethod
        def info(msg):
            infos.append(str(msg))

        @staticmethod
        def write(msg):
            writes.append(str(msg))

    loader = SimpleNamespace(
        load_json=lambda module, suffix: {
            "themes": [
                {
                    "label": "Unthemed",
                    "is_unthemed": True,
                    "quote_ids": [],
                    "conflict_event_ids": [],
                }
            ]
        }
    )
    ctx = SimpleNamespace(
        run_root=None,
        services=SimpleNamespace(content_loader=loader),
    )
    monkeypatch.setattr(oc, "st", _St)
    oc.render_highlights_compact(ctx, SimpleNamespace())
    assert writes == []
    assert infos == ["No highlight themes for this run."]


@pytest.mark.unit
def test_highlights_compact_shows_themed_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[str] = []

    class _St:
        @staticmethod
        def subheader(_title):
            return None

        @staticmethod
        def info(_msg):
            return None

        @staticmethod
        def write(msg):
            writes.append(str(msg))

    loader = SimpleNamespace(
        load_json=lambda module, suffix: {
            "themes": [
                {
                    "label": "Hiring plan",
                    "is_unthemed": False,
                    "quote_ids": ["q1"],
                    "conflict_event_ids": [],
                },
                {
                    "label": "Unthemed",
                    "is_unthemed": True,
                    "quote_ids": [],
                    "conflict_event_ids": [],
                },
            ]
        }
    )
    ctx = SimpleNamespace(
        run_root=None,
        services=SimpleNamespace(content_loader=loader),
    )
    monkeypatch.setattr(oc, "st", _St)
    oc.render_highlights_compact(ctx, SimpleNamespace())
    assert writes == ["- Hiring plan"]
