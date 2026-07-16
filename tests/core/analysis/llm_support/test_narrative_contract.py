"""Tests for the narrative output schema contract."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_support.narrative_contract import (
    parse_narrative_json,
)
from transcriptx.core.llm.errors import LLMResponseError
from tests.fixtures.llm_responses import NARRATIVE_FIXTURES, NarrativeFixture


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


@pytest.mark.unit
def test_parse_narrative_json_recovers_unescaped_inner_quotes() -> None:
    """Regression: runtime saw Expecting ',' delimiter mid-narrative prose."""
    # Match the observed shape: line 2, failure around column ~448.
    filler = "a" * 420
    raw = '{\n  "narrative": "' + filler + ' said "hello" then left."\n}'
    with pytest.raises(json.JSONDecodeError) as strict_exc:
        json.loads(raw)
    assert "Expecting ',' delimiter" in str(strict_exc.value)

    parsed = parse_narrative_json(raw)
    assert filler in parsed["narrative"]
    assert 'said "hello" then left.' in parsed["narrative"]


@pytest.mark.unit
def test_parse_narrative_json_recovers_literal_newlines() -> None:
    raw = '{\n  "narrative": "Line one.\nLine two still counts."\n}'
    parsed = parse_narrative_json(raw)
    assert "Line one." in parsed["narrative"]
    assert "Line two still counts." in parsed["narrative"]


@pytest.mark.unit
def test_parse_narrative_json_repairs_trailing_comma() -> None:
    parsed = parse_narrative_json('{"narrative": "ok",}')
    assert parsed["narrative"] == "ok"


@pytest.mark.unit
def test_parse_narrative_json_preserves_properly_escaped_quotes() -> None:
    parsed = parse_narrative_json('{"narrative": "She said \\"hi\\" clearly."}')
    assert parsed["narrative"] == 'She said "hi" clearly.'


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture",
    NARRATIVE_FIXTURES,
    ids=[f.id for f in NARRATIVE_FIXTURES],
)
def test_parse_narrative_corpus(fixture: NarrativeFixture) -> None:
    if fixture.expect == "parse_ok":
        parsed = parse_narrative_json(fixture.body)
        assert isinstance(parsed.get("narrative"), str)
        assert parsed["narrative"].strip()
    else:
        with pytest.raises(LLMResponseError):
            parse_narrative_json(fixture.body)


@pytest.mark.unit
def test_parse_narrative_json_rejects_truncated_json() -> None:
    with pytest.raises(LLMResponseError):
        parse_narrative_json('{"narrative": "The team agreed on ne')
