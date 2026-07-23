"""Unit tests for export summary body adapters (0.3.5 export polish)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.export.summary_bodies import (
    action_items_markdown,
    executive_summary_markdown,
    strip_summary_markdown,
    summary_text_from_payload,
)


@pytest.mark.unit
def test_strip_summary_markdown_drops_h1_and_footer() -> None:
    md = "# Title\n\n## Body\ntext\n\n---\nProvenance: x"
    out = strip_summary_markdown(md)
    assert out.startswith("## Body")
    assert "Title" not in out
    assert "Provenance" not in out
    assert "---" not in out


@pytest.mark.unit
def test_executive_summary_appends_commitments(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "overview": {"paragraph": "Meeting went well."},
        "commitments": {
            "items": [
                {"owner_display": "Alice", "action": "Send notes"},
                {"action": "Follow up"},
                {"owner": "Bob", "action": ""},
                "skip-me",
            ]
        },
    }
    monkeypatch.setattr(
        "transcriptx.core.analysis.summary.render_summary_markdown",
        lambda *_a, **_k: "# Exec\n\n## Overview\nMeeting went well.",
    )
    out = executive_summary_markdown(payload)
    assert "## Overview" in out
    assert "## Commitments / Next steps" in out
    assert "**Alice**: Send notes" in out
    assert "- Follow up" in out
    assert "Bob" not in out


@pytest.mark.unit
def test_executive_summary_rebuilds_from_structured_when_renderer_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.analysis.summary.render_summary_markdown",
        lambda *_a, **_k: "_No clear signal_",
    )
    payload = {
        "overview": {"paragraph": "Short overview"},
        "key_themes": {"bullets": [{"text": "Theme A"}, "Theme B", {"text": ""}]},
        "tension_points": {
            "bullets": [
                {
                    "text": "Risk",
                    "anchor_quote": {"speaker": "Carol", "quote": "wait"},
                },
                "plain tension",
            ]
        },
    }
    out = executive_summary_markdown(payload)
    assert "## Overview" in out and "Short overview" in out
    assert "## Key themes" in out and "Theme A" in out and "Theme B" in out
    assert "## Tension points" in out
    assert "**Carol**: wait" in out
    assert "plain tension" in out


@pytest.mark.unit
def test_executive_summary_falls_back_to_legacy_narrative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.analysis.summary.render_summary_markdown",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert executive_summary_markdown({"narrative": "legacy text"}) == "legacy text"


@pytest.mark.unit
def test_action_items_markdown_normalizes_empty_and_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        EMPTY_EXTRACTS_MESSAGE,
        HUMAN_REVIEW_BANNER,
    )

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.action_items_render.render_action_items_markdown",
        lambda *_a, **_k: f"_{EMPTY_EXTRACTS_MESSAGE}_",
    )
    assert action_items_markdown({"items": []}) == (
        f"{HUMAN_REVIEW_BANNER}\n\n{EMPTY_EXTRACTS_MESSAGE}"
    )

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.action_items_render.render_action_items_markdown",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad")),
    )
    out = action_items_markdown(
        {
            "items": [
                {
                    "record_type": "action_item",
                    "text": "Ship it",
                    "status": "open",
                    "owner": "Dev",
                    "deadline": "Friday",
                    "quote": "do it",
                },
                {"text": ""},
                "skip",
            ]
        }
    )
    assert HUMAN_REVIEW_BANNER in out
    assert "1. **Ship it**" in out
    assert "Status: open" in out
    assert "Owner: Dev" in out
    assert "Deadline: Friday" in out
    assert 'Quote: "do it"' in out


@pytest.mark.unit
def test_summary_text_from_payload_kind_dispatch() -> None:
    with patch(
        "transcriptx.export.summary_bodies.executive_summary_markdown",
        return_value="exec",
    ):
        assert summary_text_from_payload({}, kind="executive") == "exec"
    assert (
        summary_text_from_payload(
            {"narrative": "n1", "summary": "s1"}, kind="narrative_summary"
        )
        == "n1"
    )
    assert (
        summary_text_from_payload({"summary": "speaker"}, kind="llm_speaker_summary")
        == "speaker"
    )
    with patch(
        "transcriptx.export.summary_bodies.action_items_markdown",
        return_value="ai",
    ):
        assert summary_text_from_payload({}, kind="llm_action_items") == "ai"
    assert (
        summary_text_from_payload({"summary": "fallback"}, kind="other") == "fallback"
    )
