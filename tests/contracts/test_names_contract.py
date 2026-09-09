"""Contract tests for the names analysis module."""

from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.analysis.names import NamesAnalysis

pytestmark = pytest.mark.contract


def test_names_analysis_output_contract() -> None:
    module = NamesAnalysis()
    ner_data: dict[str, Any] = {
        "person_mentions": [
            {
                "segment_index": 0,
                "start": 0.0,
                "speaker": "Alice",
                "text": "John Smith called.",
                "surface": "John Smith",
            }
        ]
    }
    result = module.analyze(
        [{"speaker": "Alice", "text": "John Smith called.", "start": 0.0, "end": 1.0}],
        ner_data=ner_data,
    )

    assert "usable" in result
    assert "metadata" in result
    assert "people" in result
    assert "global_stats" in result
    assert "exclusions" in result

    assert isinstance(result["people"], list)
    assert isinstance(result["global_stats"], dict)
    assert isinstance(result["metadata"], dict)

    if result["people"]:
        person = result["people"][0]
        assert isinstance(person.get("display_name"), str)
        assert isinstance(person.get("normalized_key"), str)
        assert isinstance(person.get("mention_count"), int)
        assert isinstance(person.get("mentioned_by_speakers"), list)
        assert isinstance(person.get("mentions"), list)
