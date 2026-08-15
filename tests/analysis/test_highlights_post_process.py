"""Unit tests for highlights theme post-processing."""

from __future__ import annotations

from dataclasses import asdict

import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.highlights import render_highlights_markdown
from transcriptx.core.analysis.highlights.post_process import (
    assign_themes,
    stable_quote_id,
)


def _hl(
    *,
    cold_items: list | None = None,
    events: list | None = None,
    phrases: list | None = None,
    transcript_key: str = "unknown",
) -> dict:
    return {
        "transcript_key": transcript_key,
        "sections": {
            "cold_open": {"items": cold_items or []},
            "conflict_points": {"events": events or []},
            "emblematic_phrases": {"phrases": phrases or []},
        },
    }


def test_assign_themes_basic() -> None:
    phrases = [
        {
            "phrase": "budget cut",
            "score": {"total": 0.9},
        }
    ]
    cold = [
        {
            "id": "q1",
            "speaker": "A",
            "quote": "We need a budget cut now",
            "start": 1.0,
            "end": 2.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.8},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    assert groups[-1].is_unthemed is True
    themed = [g for g in groups if not g.is_unthemed]
    assert len(themed) == 1
    assert themed[0].label == "budget cut"
    assert "q1" in themed[0].quote_ids


def test_assign_themes_tier1_subsequence() -> None:
    phrases = [{"phrase": "foo bar", "score": {"total": 0.5}}]
    cold = [
        {
            "speaker": "A",
            "quote": "well foo then bar happens",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [1]},
            "score": {"total": 0.5},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    themed = [g for g in groups if not g.is_unthemed]
    assert themed and themed[0].quote_ids


def test_assign_themes_tier2_containment() -> None:
    phrases = [{"phrase": "alpha beta", "score": {"total": 0.6}}]
    cold = [
        {
            "speaker": "A",
            "quote": "alpha only here",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [2]},
            "score": {"total": 0.4},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    themed = [g for g in groups if not g.is_unthemed]
    assert themed, "50% token overlap should match tier-2"
    assert themed[0].label == "alpha beta"


def test_assign_themes_unthemed_synthetic_group() -> None:
    cold = [
        {
            "speaker": "A",
            "quote": "unrelated text here",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.3},
        }
    ]
    phrases = [{"phrase": "zzyzx qwerty", "score": {"total": 0.2}}]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    assert groups[-1].is_unthemed is True
    assert groups[-1].label == "Unthemed"
    assert len(groups[-1].quote_ids) == 1


def test_assign_themes_unthemed_empty_when_all_matched() -> None:
    phrases = [{"phrase": "hello", "score": {"total": 0.5}}]
    cold = [
        {
            "speaker": "A",
            "quote": "hello everyone",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.5},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    assert groups[-1].is_unthemed is True
    assert groups[-1].quote_ids == []


def test_assign_themes_conflict_anchor_assigns_to_theme() -> None:
    phrases = [{"phrase": "deadline", "score": {"total": 0.7}}]
    anchor = {
        "speaker": "B",
        "quote": "the deadline is Friday",
        "start": 5.0,
        "end": 6.0,
        "segment_refs": {"segment_indexes": [3]},
        "score": {"total": 0.6},
    }
    events = [
        {
            "event_id": "conflict-1",
            "start": 4.0,
            "end": 7.0,
            "participants": [{"speaker_display": "B", "speaker_id": 1}],
            "anchor_quote": anchor,
        }
    ]
    groups = assign_themes(
        _hl(cold_items=[], events=events, phrases=phrases, transcript_key="t1")
    )
    themed = [g for g in groups if not g.is_unthemed]
    assert themed
    assert "conflict-1" in themed[0].conflict_event_ids


def test_assign_themes_conflict_goes_unthemed_when_no_match() -> None:
    phrases = [{"phrase": "zzyzx", "score": {"total": 0.1}}]
    anchor = {
        "speaker": "B",
        "quote": "nothing like the phrase",
        "start": 5.0,
        "end": 6.0,
        "segment_refs": {"segment_indexes": [3]},
        "score": {"total": 0.2},
    }
    events = [
        {
            "event_id": "conflict-1",
            "start": 5.0,
            "end": 6.0,
            "participants": [{"speaker_display": "B", "speaker_id": 1}],
            "anchor_quote": anchor,
        }
    ]
    groups = assign_themes(_hl(cold_items=[], events=events, phrases=phrases))
    unthemed = groups[-1]
    assert unthemed.is_unthemed is True
    assert "conflict-1" in unthemed.conflict_event_ids


def test_assign_themes_no_phrases() -> None:
    cold = [
        {
            "speaker": "A",
            "quote": "hello",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.5},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=[]))
    assert groups[-1].is_unthemed is True
    assert len(groups[-1].quote_ids) == 1
    assert len([g for g in groups if not g.is_unthemed]) == 0


def test_assign_themes_empty_quotes() -> None:
    groups = assign_themes(_hl())
    assert len(groups) == 1
    assert groups[0].is_unthemed is True
    assert groups[0].quote_ids == []


def test_assign_themes_output_schema() -> None:
    groups = assign_themes(_hl())
    raw = [asdict(g) for g in groups]
    for row in raw:
        assert "label" in row
        assert "phrase_score" in row
        assert "is_unthemed" in row
        assert "quote_ids" in row
        assert "conflict_event_ids" in row
        assert "representative_quote_id" in row
        assert "phrase_index" in row


def test_assign_themes_no_quote_appears_twice() -> None:
    phrases = [
        {"phrase": "one two", "score": {"total": 0.9}},
        {"phrase": "three four", "score": {"total": 0.8}},
    ]
    cold = [
        {
            "id": "same",
            "speaker": "A",
            "quote": "one two three four",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.9},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    all_ids: list[str] = []
    for g in groups:
        all_ids.extend(g.quote_ids)
    assert len(all_ids) == len(set(all_ids))


def test_stable_quote_id_matches_idx_pattern() -> None:
    q = {
        "speaker": "A",
        "quote": "Hello world.",
        "segment_refs": {"segment_indexes": [3]},
    }
    sid = stable_quote_id(q, "mytalk")
    assert sid.startswith("idx:mytalk:3|")


def test_stable_quote_id_uses_db_and_uuid_refs() -> None:
    q_db = {
        "quote": "x",
        "segment_refs": {"segment_db_ids": [99]},
    }
    assert stable_quote_id(q_db, "t").startswith("db:99|")
    q_uuid = {
        "quote": "y",
        "segment_refs": {"segment_uuids": ["abc-uuid"]},
    }
    assert stable_quote_id(q_uuid, "t").startswith("uuid:abc-uuid|")


def test_attach_themes_to_highlights_mutates_payload() -> None:
    from transcriptx.core.analysis.highlights.post_process import (
        attach_themes_to_highlights,
    )

    payload = _hl()
    attach_themes_to_highlights(payload)
    assert "themes" in payload
    assert payload["themes"][-1]["is_unthemed"] is True


def test_conflict_assigned_via_overlapping_quote_when_anchor_unthemed() -> None:
    phrases = [{"phrase": "shared topic", "score": {"total": 0.8}}]
    cold = [
        {
            "speaker": "A",
            "quote": "shared topic is important",
            "start": 1.0,
            "end": 2.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.5},
        }
    ]
    anchor = {
        "speaker": "B",
        "quote": "something else entirely",
        "start": 3.0,
        "end": 4.0,
        "segment_refs": {"segment_indexes": [1]},
        "score": {"total": 0.3},
    }
    events = [
        {
            "event_id": "conflict-1",
            "start": 1.5,
            "end": 3.5,
            "participants": [{"speaker_display": "A", "speaker_id": 1}],
            "anchor_quote": anchor,
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, events=events, phrases=phrases))
    themed = [g for g in groups if not g.is_unthemed]
    assert themed
    assert "conflict-1" in themed[0].conflict_event_ids


def test_empty_phrase_string_skipped() -> None:
    phrases = [{"phrase": "   ", "score": {"total": 0.1}}]
    cold = [
        {
            "speaker": "A",
            "quote": "hello",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.5},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    assert groups[-1].quote_ids


@pytest.mark.parametrize(
    "has_themes_key",
    [True, False],
)
def test_render_markdown_key_themes_section(has_themes_key: bool) -> None:
    results = {
        "transcript_key": "unknown",
        "sections": {
            "cold_open": {
                "items": [
                    {
                        "speaker": "Emma",
                        "quote": "Let us begin.",
                        "start": 10.0,
                        "end": 15.0,
                        "segment_refs": {"segment_indexes": [3]},
                        "score": {"total": 0.7},
                    }
                ]
            },
            "conflict_points": {"events": []},
            "emblematic_phrases": {"phrases": []},
        },
    }
    if has_themes_key:
        from transcriptx.core.analysis.highlights.post_process import (
            attach_themes_to_highlights,
        )

        attach_themes_to_highlights(results)
    md = render_highlights_markdown(results)
    assert "## Key themes and moments" in md
    assert "## Cold open" in md
    assert "## Conflict points" in md
    assert "## Emblematic phrases" in md


def test_render_markdown_skips_themes_when_no_content() -> None:
    """No quotes and no phrases: early return without Key themes block."""
    results = {
        "sections": {
            "cold_open": {"items": []},
            "conflict_points": {"events": []},
            "emblematic_phrases": {"phrases": []},
        },
    }
    md = render_highlights_markdown(results)
    assert "## Key themes and moments" not in md


def test_assign_themes_filters_low_information_labels() -> None:
    phrases = [
        {"phrase": "a lot", "score": {"total": 0.9}},
        {"phrase": "i mean", "score": {"total": 0.8}},
    ]
    cold = [
        {
            "id": "q1",
            "speaker": "A",
            "quote": "we have a lot to do",
            "start": 0.0,
            "end": 1.0,
            "segment_refs": {"segment_indexes": [0]},
            "score": {"total": 0.7},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    themed_labels = [g.label for g in groups if not g.is_unthemed]
    assert "a lot" not in themed_labels
    assert "i mean" not in themed_labels
    assert groups[-1].is_unthemed is True
    assert "q1" in groups[-1].quote_ids


def test_assign_themes_keeps_valid_one_word_content_labels() -> None:
    phrases = [{"phrase": "risk", "score": {"total": 0.8}}]
    cold = [
        {
            "id": "q2",
            "speaker": "B",
            "quote": "risk is rising this quarter",
            "start": 2.0,
            "end": 3.0,
            "segment_refs": {"segment_indexes": [2]},
            "score": {"total": 0.8},
        }
    ]
    groups = assign_themes(_hl(cold_items=cold, phrases=phrases))
    themed = [g for g in groups if not g.is_unthemed]
    assert themed
    assert themed[0].label == "risk"
