"""Unit tests for Corrections Studio LLM discovery JSON contract."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.services.corrections_studio.llm.contract import (
    build_discovery_instruction,
    parse_discovery_json,
)
from tests.fixtures.llm_responses import DISCOVERY_FIXTURES, DiscoveryFixture


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture",
    DISCOVERY_FIXTURES,
    ids=[f.id for f in DISCOVERY_FIXTURES],
)
def test_parse_discovery_corpus(fixture: DiscoveryFixture) -> None:
    if fixture.expect == "parse_ok":
        got = parse_discovery_json(fixture.body)
        assert isinstance(got, list)
        assert len(got) >= fixture.min_candidates
        for row in got:
            assert "rationale" in row
            assert "short_rationale" not in row
            assert "reason" not in row
            assert "explanation" not in row
    else:
        with pytest.raises(LLMResponseError):
            parse_discovery_json(fixture.body)


@pytest.mark.unit
def test_parse_discovery_accepts_explanation_alias() -> None:
    raw = (
        '{"candidates":[{"source_text":"Foo","replacement_text":"Bar",'
        '"segment_ref":0,"explanation":"x"}]}'
    )
    got = parse_discovery_json(raw)
    assert got[0]["rationale"] == "x"


@pytest.mark.unit
def test_parse_discovery_prefers_rationale_over_alias() -> None:
    raw = (
        '{"candidates":[{"source_text":"Foo","replacement_text":"Bar",'
        '"segment_ref":0,"rationale":"keep","short_rationale":"drop"}]}'
    )
    got = parse_discovery_json(raw)
    assert got[0]["rationale"] == "keep"
    assert "short_rationale" not in got[0]


@pytest.mark.unit
def test_parse_discovery_accepts_suggestions_and_items_nests() -> None:
    for key in ("suggestions", "items"):
        raw = (
            f'{{"{key}":[{{"source_text":"Foo","replacement_text":"Bar",'
            f'"segment_ref":1,"rationale":"x"}}]}}'
        )
        got = parse_discovery_json(raw)
        assert len(got) == 1
        assert got[0]["segment_ref"] == 1


@pytest.mark.unit
def test_parse_discovery_rejects_ambiguous_alternate_nest() -> None:
    raw = (
        '{"corrections":[{"source_text":"Foo","replacement_text":"Bar",'
        '"segment_ref":0}],"meta":1}'
    )
    with pytest.raises(LLMResponseError):
        parse_discovery_json(raw)


@pytest.mark.unit
def test_parse_discovery_rejects_top_level_extra_keys() -> None:
    with pytest.raises(LLMResponseError):
        parse_discovery_json('{"candidates":[],"meta":1}')


@pytest.mark.unit
def test_parse_discovery_rejects_empty_source_or_replacement() -> None:
    with pytest.raises(LLMResponseError):
        parse_discovery_json(
            '{"candidates":[{"source_text":" ","replacement_text":"Bar","segment_ref":0}]}'
        )
    with pytest.raises(LLMResponseError):
        parse_discovery_json(
            '{"candidates":[{"source_text":"Foo","replacement_text":"","segment_ref":0}]}'
        )


@pytest.mark.unit
def test_parse_discovery_rejects_whitespace_and_non_container_roots() -> None:
    with pytest.raises(LLMResponseError):
        parse_discovery_json("   ")
    with pytest.raises(LLMResponseError):
        parse_discovery_json("42")
    with pytest.raises(LLMResponseError):
        parse_discovery_json('"just a string"')


@pytest.mark.unit
def test_parse_discovery_omitted_optional_fields() -> None:
    raw = (
        '{"candidates":[{"source_text":"Foo","replacement_text":"Bar",'
        '"segment_ref":"3"}]}'
    )
    got = parse_discovery_json(raw)
    assert got[0]["segment_ref"] == "3"
    assert got[0]["rationale"] == ""
    assert got[0]["evidence_signals"] == []


@pytest.mark.unit
def test_build_discovery_instruction_documents_candidates_shape() -> None:
    text = build_discovery_instruction(max_candidates=7)
    assert '{"candidates":' in text.replace(" ", "")
    assert "rationale (short string)" in text
    assert "short_rationale" not in text
    assert "at most 7" in text
    assert "Do not return a bare array" in text
    assert "Escape any double quotes" in text


@pytest.mark.unit
def test_parse_discovery_accepts_escaped_inner_quotes() -> None:
    raw = (
        '{"candidates":[{"source_text":"Foo \\"Bar\\"","replacement_text":"Baz",'
        '"segment_ref":0,"rationale":"said \\"Bar\\""}]}'
    )
    got = parse_discovery_json(raw)
    assert got[0]["source_text"] == 'Foo "Bar"'
    assert got[0]["rationale"] == 'said "Bar"'


@pytest.mark.unit
def test_parse_discovery_rejects_unescaped_inner_quotes() -> None:
    raw = (
        '{"candidates":[{"source_text":"Foo "Bar"","replacement_text":"Baz",'
        '"segment_ref":0,"rationale":"x"}]}'
    )
    with pytest.raises(json.JSONDecodeError) as strict_exc:
        json.loads(raw)
    assert "Expecting ',' delimiter" in str(strict_exc.value)
    with pytest.raises(LLMResponseError, match="not valid JSON"):
        parse_discovery_json(raw)


@pytest.mark.unit
def test_parse_discovery_repairs_trailing_comma() -> None:
    raw = (
        '{"candidates":[{"source_text":"Foo","replacement_text":"Bar",'
        '"segment_ref":0,"rationale":"x",}],}'
    )
    got = parse_discovery_json(raw)
    assert len(got) == 1
    assert got[0]["source_text"] == "Foo"


@pytest.mark.unit
def test_parse_discovery_rejects_truncated_json() -> None:
    with pytest.raises(LLMResponseError, match="not valid JSON"):
        parse_discovery_json(
            '{"candidates":[{"source_text":"Foo","replacement_text":"Ba'
        )
