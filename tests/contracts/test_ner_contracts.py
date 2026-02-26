"""
Contract tests for the NER analysis module (offline + deterministic).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.ner import NERAnalysis


class TestNERContracts:
    """Contract tests for NERAnalysis output shape."""

    @pytest.fixture
    def ner_module(self) -> NERAnalysis:
        """Fixture for NERAnalysis instance."""
        return NERAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with named speakers."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I live in New York and work at Google.",
                "start": 0.0,
                "end": 3.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "John Smith called from London yesterday.",
                "start": 3.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    @patch("transcriptx.core.analysis.ner.extract_named_entities")
    def test_ner_analysis_output_contract(
        self,
        mock_extract: MagicMock,
        ner_module: NERAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Assert NER analyze() result has full output contract."""

        # Deterministic entities: no spaCy required
        def side_effect(text: str) -> list[tuple[str, str]]:
            if "New York" in text and "Google" in text:
                return [("New York", "GPE"), ("Google", "ORG")]
            if "London" in text:
                return [("London", "GPE")]
            return []

        mock_extract.side_effect = side_effect

        result = ner_module.analyze(sample_segments, sample_speaker_map)

        # Top-level keys (contract)
        assert "entity_counts_per_speaker" in result
        assert "label_counts_per_speaker" in result
        assert "location_entities_per_speaker" in result
        assert "entity_sentences_per_speaker" in result
        assert "summary_json" in result
        assert "speaker_csv_rows" in result
        assert "all_rows" in result
        assert "all_label_counter" in result
        assert "entities" in result
        assert "segments" in result

        # Types and minimal structure checks
        assert isinstance(result["entity_counts_per_speaker"], dict)
        assert isinstance(result["label_counts_per_speaker"], dict)
        assert isinstance(result["all_label_counter"], dict)
        assert isinstance(result["entities"], list)
        assert result["segments"] is sample_segments
