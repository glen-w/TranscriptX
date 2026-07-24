"""Contract tests for weak analysis module contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

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
            "id": "1",
            "nrc_emotion": {"joy": 0.9, "sadness": 0.1},
            "emotion_evaluation_state": "scored",
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "I am happy too.",
            "start": 1.0,
            "end": 2.0,
            "id": "2",
            "nrc_emotion": {"joy": 0.8, "sadness": 0.2},
            "emotion_evaluation_state": "scored",
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
    assert isinstance(result["contagion_counts"], list)
    assert all(
        set(item) >= {"actor", "target", "emotion", "count"}
        for item in result["contagion_counts"]
    )
    assert isinstance(result["timeline"], list)
    assert len(result["timeline"]) == len(segments)


def test_contagion_not_applicable_envelope_contract() -> None:
    module = ContagionAnalysis()
    context = SimpleNamespace(
        transcript_path="/tmp/input.json",
        get_segments=lambda: [{"speaker": "A", "text": "x"}],
        get_speaker_map=lambda: {},
        get_analysis_result=lambda _name: None,
        get_computed_value=lambda _key: None,
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda _name, _results: None,
    )
    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(module_dir="/tmp/c")
    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=fake_out,
        ),
        patch.object(module, "save_results"),
    ):
        result = module.run_from_context(context)
    assert result["module"] == "contagion"
    assert result["status"] == "success"
    assert result["results"]["run_status"] == "not_applicable"
    assert result["results"]["usable_output"] is False


def test_entity_sentiment_success_schema_and_summary_invariants() -> None:
    pytest.importorskip("spacy")

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


def test_semantic_similarity_v2_single_speaker_repetition_skip_contract() -> None:
    """V2 still runs for single speaker but skips the repetition pair path."""
    module = SemanticSimilarityAnalysis()
    stored: dict[str, dict] = {}
    context = SimpleNamespace(
        transcript_path="/tmp/input.json",
        get_segments=lambda: [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "one"},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "two"},
        ],
        get_analysis_result=lambda _name: None,
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda name, payload: stored.setdefault(name, payload),
    )
    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(
        module_dir="/tmp/sem", charts_dir="/tmp/sem/charts"
    )
    stub_results = {
        "speaker_repetitions": {},
        "cross_speaker_repetitions": [],
        "repetition_path": "skipped",
        "repetition_skip_reason": "single_identified_speaker",
    }
    stub_diag = MagicMock()
    stub_diag.runtime_seconds_breakdown = {"total": 0.01}
    stub_diag.to_dict.return_value = {}
    fake_out.get_artifacts.return_value = []
    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=fake_out,
        ),
        patch(
            "transcriptx.core.analysis.semantic_similarity.analysis.resolve_semantic_similarity_runtime",
            return_value=(MagicMock(), MagicMock()),
        ),
        patch(
            "transcriptx.core.analysis.semantic_similarity.analysis.run_semantic_similarity_pipeline",
            return_value=(stub_results, stub_diag),
        ) as pipeline,
        patch(
            "transcriptx.core.analysis.semantic_similarity.analysis.create_visualizations",
            return_value=[],
        ),
        patch.object(module, "save_results"),
    ):
        result = module.run_from_context(context)
    assert pipeline.call_args.kwargs.get("repetition_path_skipped") is True
    assert result["module_name"] == "semantic_similarity"
    assert result["status"] in {"success", "partial", "error", "blocked"}
    assert stored.get("semantic_similarity") is not None
    payload = stored["semantic_similarity"]
    assert (
        payload.get("repetition_path") == "skipped"
        or payload.get("repetition_skip_reason") == "single_identified_speaker"
    )
