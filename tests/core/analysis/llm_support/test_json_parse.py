"""Tests for generic LLM JSON fence stripping and light repair."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_support.json_parse import (
    loads_llm_json,
    loads_llm_json_document,
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


@pytest.mark.unit
def test_loads_llm_json_accepts_bare_array() -> None:
    assert loads_llm_json('[{"a": 1}]') == [{"a": 1}]


@pytest.mark.unit
def test_loads_llm_json_raises_on_truncated_object() -> None:
    with pytest.raises(json.JSONDecodeError):
        loads_llm_json('{"candidates":[{"source_text":"a"')


@pytest.mark.unit
def test_loads_llm_json_bare_array_trailing_junk_may_extract_nested_object() -> None:
    # After json.loads fails, raw_decode starts at the first '{', so a trailing
    # junk array can accidentally yield the first nested object.
    assert loads_llm_json('[{"a": 1}] trailing prose') == {"a": 1}


@pytest.mark.unit
def test_loads_llm_json_document_rejects_trailing_junk() -> None:
    with pytest.raises(json.JSONDecodeError):
        loads_llm_json_document('{"a": 1} trailing prose')


@pytest.mark.unit
def test_loads_llm_json_document_repairs_trailing_comma() -> None:
    assert loads_llm_json_document('{"narrative": "ok",}') == {"narrative": "ok"}


@pytest.mark.unit
def test_loads_llm_json_document_rejects_prose_wrapped() -> None:
    raw = 'Here is JSON:\n```json\n{"narrative": "ok"}\n```\nThanks!'
    with pytest.raises(json.JSONDecodeError):
        loads_llm_json_document(raw)


@pytest.mark.unit
def test_loads_llm_json_repairs_missing_comma_between_arrays() -> None:
    assert loads_llm_json('{"items": [[1] [2]]}') == {"items": [[1], [2]]}


@pytest.mark.unit
def test_strip_json_fence_case_insensitive_lang_tag() -> None:
    raw = '```JSON\n{"ok": true}\n```'
    assert strip_json_fence(raw) == '{"ok": true}'


@pytest.mark.unit
def test_loads_llm_json_document_accepts_fenced_object() -> None:
    raw = '```json\n{"narrative": "ok"}\n```'
    assert loads_llm_json_document(raw) == {"narrative": "ok"}


@pytest.mark.unit
def test_loads_llm_json_raises_on_unescaped_inner_quotes() -> None:
    raw = '{"text": "She said "hello" then left."}'
    with pytest.raises(json.JSONDecodeError) as exc:
        loads_llm_json(raw)
    assert "Expecting ',' delimiter" in str(exc.value)


@pytest.mark.unit
def test_loads_llm_json_document_raises_on_unescaped_inner_quotes() -> None:
    raw = '{"narrative": "She said "hello" then left."}'
    with pytest.raises(json.JSONDecodeError) as exc:
        loads_llm_json_document(raw)
    assert "Expecting ',' delimiter" in str(exc.value)
