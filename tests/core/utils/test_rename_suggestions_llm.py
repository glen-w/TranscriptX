"""LLM parse rules for rename suggestions."""

from __future__ import annotations

import json

from transcriptx.core.utils.rename.suggestions.llm import (
    RENAME_LLM_SUGGESTION_COUNT,
    parse_llm_rename_cue,
    parse_llm_rename_cues,
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
