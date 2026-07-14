"""Tests for generic LLM JSON fence stripping and light repair."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_support.json_parse import (
    loads_llm_json,
    strip_json_fence,
)


@pytest.mark.unit
def test_strip_json_fence_only() -> None:
    raw = '```json\n{"narrative": "ok"}\n```'
    assert strip_json_fence(raw) == '{"narrative": "ok"}'


@pytest.mark.unit
def test_strip_json_fence_does_not_extract_from_prose() -> None:
    raw = 'Here is JSON:\n```json\n{"narrative": "ok"}\n```\nThanks!'
    assert strip_json_fence(raw) == raw.strip()


@pytest.mark.unit
def test_loads_llm_json_strict_first() -> None:
    assert loads_llm_json('{"items": []}') == {"items": []}


@pytest.mark.unit
def test_loads_llm_json_repairs_trailing_comma() -> None:
    assert loads_llm_json('{"items": [1, 2,]}') == {"items": [1, 2]}


@pytest.mark.unit
def test_loads_llm_json_repairs_missing_comma_between_objects() -> None:
    assert loads_llm_json('{"items": [{"a": 1} {"a": 2}]}') == {
        "items": [{"a": 1}, {"a": 2}]
    }


@pytest.mark.unit
def test_loads_llm_json_tolerates_trailing_junk() -> None:
    assert loads_llm_json('{"a": 1} trailing prose') == {"a": 1}


@pytest.mark.unit
def test_loads_llm_json_raises_on_garbage() -> None:
    with pytest.raises(json.JSONDecodeError):
        loads_llm_json("no json here")
