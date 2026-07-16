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
