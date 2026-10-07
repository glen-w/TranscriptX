"""LLM parse rules for rename suggestions."""

from __future__ import annotations

import json
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from transcriptx.core.utils.rename.suggestions.llm import (
    RENAME_LLM_JSON_SCHEMA,
    RENAME_LLM_SUGGESTION_COUNT,
    parse_llm_rename_cue,
    parse_llm_rename_cues,
    run_rename_llm,
)


def test_llm_date_dropped_without_quote() -> None:
    raw = '{"event_date": "2026-03-12", "title": "Acme Webinar", "quote": ""}'
    cue = parse_llm_rename_cue(raw, excerpt="Welcome everyone.")
    assert cue is not None
    assert cue.event_date is None
    assert cue.title == "Acme Webinar"


def test_llm_date_kept_with_matching_quote() -> None:
    excerpt = "Recorded on 2026-03-12 for the launch."
    raw = (
        '{"event_date": "2026-03-12", "title": "Launch", '
        '"quote": "Recorded on 2026-03-12"}'
    )
    cue = parse_llm_rename_cue(raw, excerpt=excerpt)
    assert cue is not None
    assert cue.event_date is not None
    assert cue.event_date.isoformat() == "2026-03-12"


def test_llm_parses_three_distinct_suggestions() -> None:
    excerpt = "Welcome to the Acme marine policy webinar."
    raw = json.dumps(
        {
            "suggestions": [
                {"title": "Marine Policy", "event_date": None, "quote": ""},
                {"title": "Acme Webinar", "event_date": None, "quote": ""},
                {"title": "Ocean Governance", "event_date": None, "quote": ""},
            ]
        }
    )
    cues = parse_llm_rename_cues(raw, excerpt=excerpt)
    assert len(cues) == RENAME_LLM_SUGGESTION_COUNT
    assert {c.title for c in cues} == {
        "Marine Policy",
        "Acme Webinar",
        "Ocean Governance",
    }
    assert cues[0].detail == "Local LLM suggestion 1"
    assert cues[2].detail == "Local LLM suggestion 3"


@pytest.mark.unit
def test_run_rename_llm_uses_keyword_generate_and_schema() -> None:
    excerpt = "Welcome to the Acme marine policy webinar."
    payload = json.dumps(
        {
            "suggestions": [
                {"title": "Marine Policy", "event_date": None, "quote": ""},
                {"title": "Acme Webinar", "event_date": None, "quote": ""},
                {"title": "Ocean Governance", "event_date": None, "quote": ""},
            ]
        }
    )
    captured: dict[str, Any] = {}

    def _generate(
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Any = None,
    ) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["response_format"] = response_format
        captured["temperature"] = temperature
        captured["max_tokens"] = max_tokens
        return payload

    client = MagicMock()
    client.generate.side_effect = _generate
    cues, err = run_rename_llm(
        client,
        user_prompt="excerpt body",
        excerpt_for_quotes=excerpt,
        temperature=0.2,
        max_tokens=512,
    )
    assert err is None
    assert len(cues) == RENAME_LLM_SUGGESTION_COUNT
    assert captured["prompt"] == "excerpt body"
    assert captured["system_prompt"]
    assert captured["response_format"] == RENAME_LLM_JSON_SCHEMA
    client.generate.assert_called_once()


@pytest.mark.unit
def test_run_rename_llm_surfaces_typeerror() -> None:
    client = MagicMock()
    client.generate.side_effect = TypeError(
        "LLMClient.generate() got multiple values for argument 'temperature'"
    )
    cues, err = run_rename_llm(
        client,
        user_prompt="x",
        excerpt_for_quotes="y",
        temperature=0.0,
        max_tokens=64,
    )
    assert cues == []
    assert err is not None
    assert "multiple values" in err
    assert client.generate.call_count == 2  # schema then format=json


@pytest.mark.unit
def test_run_rename_llm_falls_back_to_json_format() -> None:
    excerpt = "Welcome to the Acme marine policy webinar."
    payload = json.dumps(
        {
            "suggestions": [
                {"title": "Marine Policy", "event_date": None, "quote": ""},
                {"title": "Acme Webinar", "event_date": None, "quote": ""},
                {"title": "Ocean Governance", "event_date": None, "quote": ""},
            ]
        }
    )
    formats: list[Any] = []

    def _generate(
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Any = None,
    ) -> str:
        formats.append(response_format)
        if isinstance(response_format, dict):
            raise RuntimeError("schema unsupported")
        return payload

    client = MagicMock()
    client.generate.side_effect = _generate
    cues, err = run_rename_llm(
        client,
        user_prompt="excerpt body",
        excerpt_for_quotes=excerpt,
        temperature=0.1,
        max_tokens=256,
    )
    assert err is None
    assert len(cues) == RENAME_LLM_SUGGESTION_COUNT
    assert formats[0] == RENAME_LLM_JSON_SCHEMA
    assert formats[1] == "json"


@pytest.mark.unit
def test_run_rename_llm_reports_unusable_json() -> None:
    client = MagicMock()
    client.generate.return_value = '{"suggestions":[]}'
    cues, err = run_rename_llm(
        client,
        user_prompt="x",
        excerpt_for_quotes="Welcome",
        temperature=0.0,
        max_tokens=64,
    )
    assert cues == []
    assert err is not None
    assert "usable rename suggestions" in err
