"""Tests for meeting-extract markdown rendering (core and export variants)."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.action_items_contract import (
    EMPTY_EXTRACTS_MESSAGE,
    HUMAN_REVIEW_BANNER,
    LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
    TITLE_MEETING_EXTRACTS,
)
from transcriptx.core.analysis.llm_support.action_items_render import (
    escape_markdown,
    render_action_items_markdown,
)


def _payload() -> dict:
    return {
        "schema_id": "transcriptx.llm_action_items.v1",
        "render_contract_id": LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
        "items": [
            {
                "record_type": "action_item",
                "text": "Send *the* report",
                "owner": "Alice",
                "deadline": "Friday",
                "status": "open",
                "quote": "I will send the report by Friday.",
                "confidence": 0.9,
            }
        ],
        "provenance": {
            "prompt_version": "5",
            "model": "qwen3:8b",
            "render_contract_id": LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
        },
    }


@pytest.mark.unit
def test_escape_markdown_escapes_special_chars() -> None:
    assert escape_markdown("a*b_c[d]") == r"a\*b\_c\[d\]"


@pytest.mark.unit
def test_render_action_items_markdown_escapes_and_includes_meta() -> None:
    md = render_action_items_markdown(_payload())
    assert md.startswith(f"# {TITLE_MEETING_EXTRACTS}")
    assert HUMAN_REVIEW_BANNER in md
    assert r"Send \*the\* report" in md
    assert "Confidence: 0.90" in md
    assert "Prompt version: 5" in md
    assert "Model: qwen3:8b" in md
    assert f"Render contract: {LLM_ACTION_ITEMS_RENDER_CONTRACT_ID}" in md


@pytest.mark.unit
def test_render_action_items_markdown_without_meta_keeps_banner() -> None:
    md = render_action_items_markdown(_payload(), include_meta=False)
    assert HUMAN_REVIEW_BANNER in md
    assert "Confidence:" not in md
    assert "Prompt version:" not in md
    assert "Model:" not in md
    assert "Render contract:" not in md


@pytest.mark.unit
def test_render_action_items_markdown_empty_items() -> None:
    md = render_action_items_markdown({"items": []})
    assert f"_{EMPTY_EXTRACTS_MESSAGE}_" in md
    assert HUMAN_REVIEW_BANNER in md
