"""Contract tests for weak analysis module contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


from transcriptx.core.analysis.contagion import ContagionAnalysis
from transcriptx.core.analysis.entity_sentiment import EntitySentimentAnalysis
from transcriptx.core.analysis.semantic_similarity.analysis import (
    SemanticSimilarityAnalysis,
)


def test_contagion_success_shape_and_invariants_contract() -> None:
    module = ContagionAnalysis()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Great news.",
            "start": 0.0,
            "end": 1.0,
            "context_emotion": {"joy": 0.9, "sadness": 0.1},
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "I am happy too.",
            "start": 1.0,
            "end": 2.0,
            "context_emotion": {"joy": 0.8, "sadness": 0.2},
        },
    ]
    result = module.analyze(segments)

    required = {
        "contagion_events",
        "contagion_counts",
        "contagion_summary",
        "emotion_type",
        "timeline",
        "speaker_emotions",
    }
    assert required.issubset(result.keys())
    assert isinstance(result["contagion_events"], list)
    assert isinstance(result["contagion_counts"], dict)
    assert isinstance(result["timeline"], list)
    assert len(result["timeline"]) == len(segments)


def test_contagion_error_envelope_contract() -> None:
    module = ContagionAnalysis()
    context = SimpleNamespace(
        transcript_path="/tmp/input.json",
        get_segments=lambda: [{"speaker": "A", "text": "x"}],
        get_speaker_map=lambda: {},
        get_analysis_result=lambda _name: None,
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda _name, _results: None,
    )
    result = module.run_from_context(context)
    assert result["module"] == "contagion"
    assert result["status"] == "error"
    assert isinstance(result.get("error"), str)
    assert result.get("results") == {}


def test_entity_sentiment_success_schema_and_summary_invariants() -> None:
    module = EntitySentimentAnalysis()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Python is excellent. Python helps teams.",
            "start": 0.0,
            "end": 2.0,
        }
    ]
    with patch(
        "transcriptx.core.analysis.entity_sentiment.extract_named_entities",
        return_value=[("Python", "ORG"), ("Python", "ORG")],
    ):
        with patch(
            "transcriptx.core.analysis.entity_sentiment.score_sentiment",
            return_value={"compound": 0.5, "pos": 0.6, "neu": 0.3, "neg": 0.1},
        ):
            result = module.analyze(segments)

    required = {
        "entity_stats",
        "total_entities",
        "total_mentions",
        "entity_sentiment",
        "entities",
        "speaker_entity_sentiment",
        "speaker_mentions",
        "summary",
    }
    assert required.issubset(result.keys())
    assert result["summary"]["total_entities"] == result["total_entities"]
    assert result["summary"]["total_mentions"] == result["total_mentions"]
    if result["entity_stats"]:
        first = next(iter(result["entity_stats"].values()))
        assert "mention_count" in first
        assert "speaker_breakdown" in first


def test_semantic_similarity_single_speaker_skip_envelope_contract() -> None:
    with patch(
        "transcriptx.core.analysis.semantic_similarity.analysis.SemanticSimilarityAnalyzer"
    ):
        module = SemanticSimilarityAnalysis()
    stored: dict[str, dict] = {}
    context = SimpleNamespace(
        transcript_path="/tmp/input.json",
        get_segments=lambda: [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "one"},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "two"},
        ],
        store_analysis_result=lambda name, payload: stored.setdefault(name, payload),
    )
    result = module.run_from_context(context)
    assert result["module_name"] == "semantic_similarity"
    assert result["status"] == "success"
    assert result["metrics"]["skipped"] is True
    assert result["metrics"]["reason"] == "single_identified_speaker"
    assert stored.get("semantic_similarity") == {}
