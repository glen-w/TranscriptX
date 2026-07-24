"""Unit tests for chart_descriptions LLM JSON response parsing."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.chart_descriptions.generate import (
    _parse_description_json,
)


@pytest.mark.unit
def test_parse_description_json_accepts_plain_object() -> None:
    assert (
        _parse_description_json('{"description": "Bars rise mid-meeting."}', max_chars=200)
        == "Bars rise mid-meeting."
    )


@pytest.mark.unit
def test_parse_description_json_strips_fence() -> None:
    raw = '```json\n{"description": "Peak at 12:00."}\n```'
    assert _parse_description_json(raw, max_chars=200) == "Peak at 12:00."


@pytest.mark.unit
def test_parse_description_json_truncates_to_max_chars() -> None:
    body = "x" * 50
    out = _parse_description_json(
        f'{{"description": "{body}"}}',
        max_chars=10,
    )
    assert out == "x" * 10


@pytest.mark.unit
def test_parse_description_json_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_description_json('{"description": "unterminated', max_chars=200)


@pytest.mark.unit
def test_parse_description_json_rejects_missing_field() -> None:
    with pytest.raises(ValueError, match="missing description"):
        _parse_description_json('{"text": "nope"}', max_chars=200)


@pytest.mark.unit
def test_parse_description_json_rejects_empty_description() -> None:
    with pytest.raises(ValueError, match="empty description"):
        _parse_description_json('{"description": "   "}', max_chars=200)


@pytest.mark.unit
def test_parse_description_json_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="missing description"):
        _parse_description_json('["description"]', max_chars=200)
