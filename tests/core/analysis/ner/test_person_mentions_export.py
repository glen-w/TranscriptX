"""Tests for NER person_mentions export."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.ner import NERAnalysis

pytestmark = pytest.mark.unit


@patch("transcriptx.core.analysis.ner.extract_named_entities")
def test_ner_exports_person_mentions(mock_extract: MagicMock) -> None:
    def side_effect(text: str) -> list[tuple[str, str]]:
        if "John Smith" in text:
            return [("John Smith", "PERSON")]
        return []

    mock_extract.side_effect = side_effect
    module = NERAnalysis()
    segments: list[dict[str, Any]] = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "John Smith called from London.",
            "start": 0.0,
            "end": 3.0,
        }
    ]
    result = module.analyze(segments)
    assert "person_mentions" in result
    assert len(result["person_mentions"]) == 1
    mention = result["person_mentions"][0]
    assert mention["surface"] == "John Smith"
    assert mention["segment_index"] == 0
    assert mention["speaker"] == "Alice"
