"""Tests for action-items markdown rendering (core and export variants)."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.action_items_render import (
    escape_markdown,
    render_action_items_markdown,
)


def _payload() -> dict:
    return {
        "items": [
            {
                "text": "Send *the* report",
                "owner": "Alice",
                "deadline": "Friday",
                "status": "open",
                "quote": "I will send the report by Friday.",
                "confidence": 0.9,
            }
        ],
        "provenance": {"prompt_version": "2", "model": "qwen3:8b"},
    }


@pytest.mark.unit
def test_escape_markdown_escapes_special_chars() -> None:
    assert escape_markdown("a*b_c[d]") == r"a\*b\_c\[d\]"


@pytest.mark.unit
def test_render_action_items_markdown_escapes_and_includes_meta() -> None:
    md = render_action_items_markdown(_payload())
    assert md.startswith("# Action Items")
    assert r"Send \*the\* report" in md
    assert "Confidence: 0.90" in md
    assert "Prompt version: 2" in md
    assert "Model: qwen3:8b" in md


@pytest.mark.unit
def test_render_action_items_markdown_without_meta_for_export() -> None:
    md = render_action_items_markdown(_payload(), include_meta=False)
    assert "Confidence:" not in md
    assert "Prompt version:" not in md
    assert "Model:" not in md


@pytest.mark.unit
def test_render_action_items_markdown_empty_items() -> None:
    md = render_action_items_markdown({"items": []})
    assert "_No action items found._" in md
