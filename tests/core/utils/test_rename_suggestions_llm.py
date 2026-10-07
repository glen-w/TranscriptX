"""LLM parse rules for rename suggestions."""

from __future__ import annotations

from transcriptx.core.utils.rename.suggestions.llm import parse_llm_rename_cue


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
