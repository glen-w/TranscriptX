"""Tests for the action-items contract: parsing strictness, grounding, dedupe,
ordering, and cache-key identity."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_support.action_items_contract import (
    build_llm_action_items_cache_key,
    dedupe_action_items,
    ground_action_items,
    order_action_items,
    parse_action_items_json,
)
from transcriptx.core.llm.errors import LLMResponseError


def _item(**overrides: object) -> dict:
    base = {
        "text": "Send the report",
        "owner": "Alice",
        "deadline": "Friday",
        "status": "open",
        "quote": "I will send the report by Friday.",
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_build_llm_action_items_cache_key_golden() -> None:
    cache_key = build_llm_action_items_cache_key(
        module_version="1.0.0",
        prompt_version="v1",
        schema_id="action_items_v1",
        transcript_fingerprint="tf",
        bounded_input_fingerprint="bf",
        model="qwen3:8b",
        runtime={"max_input_chars": 48000},
        generation_options={"temperature": 0.0},
        llm_request_sha256="rh",
    )
    assert (
        cache_key == "adca868f7de308fd306681794caca189674b2595363563bfc2908e730bf0edb2"
    )


@pytest.mark.unit
def test_parse_action_items_rejects_unknown_item_keys() -> None:
    payload = json.dumps({"items": [_item(surprise=1)]})
    with pytest.raises(LLMResponseError, match="unexpected keys"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_parse_action_items_rejects_unknown_top_level_keys() -> None:
    payload = json.dumps({"items": [], "extra": True})
    with pytest.raises(LLMResponseError, match="unexpected keys"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_parse_action_items_rejects_non_finite_confidence() -> None:
    payload = '{"items": [%s]}' % json.dumps(_item()).replace("0.9", "NaN")
    with pytest.raises(LLMResponseError, match="finite"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_parse_action_items_rejects_boolean_confidence() -> None:
    payload = json.dumps({"items": [_item(confidence=True)]})
    with pytest.raises(LLMResponseError, match="must be a number"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_parse_action_items_rejects_out_of_range_confidence() -> None:
    payload = json.dumps({"items": [_item(confidence=1.5)]})
    with pytest.raises(LLMResponseError, match=r"\[0, 1\]"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_parse_action_items_rejects_invalid_status() -> None:
    payload = json.dumps({"items": [_item(status="paused")]})
    with pytest.raises(LLMResponseError, match="open, done, unclear"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_parse_action_items_enforces_output_length_gate() -> None:
    payload = json.dumps({"items": [_item()]})
    with pytest.raises(LLMResponseError, match="exceeds expected length"):
        parse_action_items_json(payload, max_output_tokens=1)


@pytest.mark.unit
def test_ground_action_items_nulls_ungrounded_quote_and_halves_confidence() -> None:
    items = [_item(text="send the report by Friday", quote="Fabricated quote.")]
    transcript = "Alice: I will send the report by Friday."
    grounded, diagnostics = ground_action_items(items, transcript)
    assert len(grounded) == 1
    assert grounded[0]["quote"] is None
    assert grounded[0]["confidence"] == pytest.approx(0.45)
    assert diagnostics["quotes_nulled"] == 1


@pytest.mark.unit
def test_order_action_items_by_transcript_offset_and_strips_model_index() -> None:
    transcript = "Alice: first task here. Bob: second task here."
    items = [
        dict(_item(text="second task here", quote=None), _model_index=0),
        dict(_item(text="first task here", quote=None), _model_index=1),
    ]
    ordered = order_action_items(items, transcript)
    assert [i["text"] for i in ordered] == ["first task here", "second task here"]
    assert all("_model_index" not in i for i in ordered)


@pytest.mark.unit
def test_dedupe_action_items_keeps_quoted_over_unquoted() -> None:
    items = [
        _item(quote=None, confidence=0.95),
        _item(confidence=0.6),
    ]
    deduped = dedupe_action_items(items)
    assert len(deduped) == 1
    assert deduped[0]["quote"] is not None
