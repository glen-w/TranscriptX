"""Unit tests for names catalog builder."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.names.catalog import build_names_catalog

pytestmark = pytest.mark.unit


def test_build_names_catalog_dedupes_and_counts() -> None:
    mentions = [
        {
            "segment_index": 0,
            "start": 0.0,
            "speaker": "Alice",
            "text": "John called earlier.",
            "surface": "John",
        },
        {
            "segment_index": 1,
            "start": 3.0,
            "speaker": "Bob",
            "text": "John Smith is visiting.",
            "surface": "John Smith",
        },
        {
            "segment_index": 2,
            "start": 6.0,
            "speaker": "Alice",
            "text": "Ask John about it.",
            "surface": "John",
        },
    ]
    result = build_names_catalog(mentions)
    assert result["global_stats"]["unique_people"] == 2
    assert result["global_stats"]["total_mentions"] == 3
    by_key = {person["normalized_key"]: person for person in result["people"]}
    assert by_key["john"]["mention_count"] == 2
    assert by_key["john smith"]["mention_count"] == 1
    assert by_key["john"]["mentioned_by_speakers"] == ["Alice"]
    assert by_key["john smith"]["mentioned_by_speakers"] == ["Bob"]


def test_build_names_catalog_min_mentions_filter() -> None:
    mentions = [
        {
            "segment_index": 0,
            "start": 0.0,
            "speaker": "Alice",
            "text": "John called.",
            "surface": "John",
        },
        {
            "segment_index": 1,
            "start": 3.0,
            "speaker": "Bob",
            "text": "Maya called.",
            "surface": "Maya",
        },
        {
            "segment_index": 2,
            "start": 6.0,
            "speaker": "Alice",
            "text": "John again.",
            "surface": "John",
        },
    ]
    result = build_names_catalog(mentions, min_mentions=2)
    assert result["global_stats"]["unique_people"] == 1
    assert result["people"][0]["display_name"] == "John"


def test_build_names_catalog_exclude_known_speakers() -> None:
    mentions = [
        {
            "segment_index": 0,
            "start": 0.0,
            "speaker": "Alice",
            "text": "Alice is here.",
            "surface": "Alice",
        },
        {
            "segment_index": 1,
            "start": 3.0,
            "speaker": "Bob",
            "text": "John called.",
            "surface": "John",
        },
    ]
    segments = [
        {"speaker": "Alice", "text": "hi", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "hey", "start": 1.0, "end": 2.0},
    ]
    result = build_names_catalog(
        mentions,
        segments=segments,
        exclude_known_speakers=True,
    )
    assert result["global_stats"]["unique_people"] == 1
    assert result["people"][0]["display_name"] == "John"


def test_build_names_catalog_caps_mentions() -> None:
    mentions = [
        {
            "segment_index": i,
            "start": float(i),
            "speaker": "Alice",
            "text": f"John line {i}",
            "surface": "John",
        }
        for i in range(5)
    ]
    result = build_names_catalog(mentions, max_mentions_per_person=2)
    assert len(result["people"][0]["mentions"]) == 2
