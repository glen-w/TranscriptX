"""
Contract tests for lexical emotion v2 (offline + deterministic).
"""

from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.analysis.emotion import EmotionAnalysis


class TestEmotionLexicalContracts:
    """Contract tests for EmotionAnalysis lexical v2 output shape."""

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "a1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm so happy about this!",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "id": "b1",
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "This makes me angry and sad.",
                "start": 2.0,
                "end": 4.0,
            },
        ]

    def test_emotion_output_contract(
        self, sample_segments: list[dict[str, Any]]
    ) -> None:
        pytest.importorskip("nrclex")
        emotion_module = EmotionAnalysis()
        result = emotion_module.analyze(sample_segments)

        assert result["schema_version"] == "emotion_result_schema_v2"
        assert result["semantics_version"] == "emotion_lexical_v2"
        assert "run_status" in result
        assert "usable_output" in result
        assert "segments_with_emotion" in result
        assert "nrc_scores" in result
        assert "combined_rows" in result
        assert "all_scores" in result
        assert "speaker_stats" in result
        assert "global_stats" in result
        # Full vectors live in generational store; analyze keeps private rows only
        assert "_canonical_rows" in result
        assert "canonical_rows" not in result
        assert "compatibility_fingerprint" in result
        assert "tokens_considered" in result["global_stats"]
        assert "mean_coverage" in result["global_stats"]

        assert isinstance(result["segments_with_emotion"], list)
        assert isinstance(result["nrc_scores"], dict)
        assert isinstance(result["global_stats"], dict)
        assert result.get("_pending_projections")
        assert "lexicon_digest" in result
        assert "nrclex_version" in result
        assert "projection_fields" in result

        # Owned projection fields are deferred until canonical persist.
        for seg in result["segments_with_emotion"]:
            assert "nrc_emotion" not in seg
            assert "context_emotion_source" not in seg
            assert "context_emotion_primary" not in seg

        from transcriptx.core.analysis.emotion.projections import (
            apply_lexical_projection,
        )
        from transcriptx.core.analysis.emotion_family.persist import (
            apply_pending_projections,
        )

        apply_pending_projections(result, apply_one=apply_lexical_projection)
        for seg in result["segments_with_emotion"]:
            assert "nrc_emotion" in seg
            assert "context_emotion_source" not in seg
            assert "context_emotion_primary" not in seg
