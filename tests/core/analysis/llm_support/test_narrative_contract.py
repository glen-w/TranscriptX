"""Tests for the narrative output schema contract."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.narrative_contract import (
    parse_narrative_json,
)
from transcriptx.core.llm.errors import LLMResponseError


@pytest.mark.unit
def test_parse_narrative_json_rejects_prose_wrapped() -> None:
    raw = 'Here is JSON:\n```json\n{"narrative": "ok"}\n```\nThanks!'
    with pytest.raises(LLMResponseError):
        parse_narrative_json(raw)


@pytest.mark.unit
def test_parse_narrative_json_accepts_fenced() -> None:
    raw = '```json\n{"narrative": "Executive update."}\n```'
    parsed = parse_narrative_json(raw)
    assert parsed["narrative"] == "Executive update."


@pytest.mark.unit
def test_parse_narrative_json_accepts_raw_json_without_fence() -> None:
    parsed = parse_narrative_json('{"narrative": "Plain JSON works."}')
    assert parsed["narrative"] == "Plain JSON works."


@pytest.mark.unit
def test_parse_narrative_json_rejects_extra_keys() -> None:
    with pytest.raises(LLMResponseError, match="unexpected keys"):
        parse_narrative_json('{"narrative": "ok", "extra": 1}')


@pytest.mark.unit
def test_parse_narrative_json_rejects_non_object() -> None:
    with pytest.raises(LLMResponseError, match="must be an object"):
        parse_narrative_json('["not", "an", "object"]')


@pytest.mark.unit
def test_parse_narrative_json_rejects_empty_narrative() -> None:
    with pytest.raises(LLMResponseError, match="non-empty"):
        parse_narrative_json('{"narrative": "   "}')


@pytest.mark.unit
def test_parse_narrative_json_enforces_output_length_gate() -> None:
    long_text = "x" * 100
    with pytest.raises(LLMResponseError, match="exceeds expected length"):
        parse_narrative_json(
            f'{{"narrative": "{long_text}"}}',
            max_output_tokens=10,
        )
