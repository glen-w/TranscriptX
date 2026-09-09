"""Unit tests for NamesAnalysis."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.names import NamesAnalysis

pytestmark = pytest.mark.unit


def test_analyze_missing_ner_is_not_usable() -> None:
    module = NamesAnalysis()
    result = module.analyze([{"speaker": "Alice", "text": "hi", "start": 0, "end": 1}])
    assert result["usable"] is False
    assert result["exclusions"]["reason"] == "missing_ner_result"


def test_analyze_builds_catalog_from_ner_payload() -> None:
    module = NamesAnalysis()
    segments = [
        {"speaker": "Alice", "text": "John called.", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Thanks John.", "start": 1.0, "end": 2.0},
    ]
    ner_data = {
        "person_mentions": [
            {
                "segment_index": 0,
                "start": 0.0,
                "speaker": "Alice",
                "text": "John called.",
                "surface": "John",
            },
            {
                "segment_index": 1,
                "start": 1.0,
                "speaker": "Bob",
                "text": "Thanks John.",
                "surface": "John",
            },
        ]
    }
    result = module.analyze(segments, ner_data=ner_data)
    assert result["usable"] is True
    assert result["global_stats"]["unique_people"] == 1
    assert result["people"][0]["mention_count"] == 2
    assert result["metadata"]["schema_id"] == "transcriptx.names.v1"
