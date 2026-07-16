"""Offline unit tests for semantic similarity analyzer classes (mocked models)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.semantic_similarity import analyzers as az


def _cfg(**overrides):
    analysis = SimpleNamespace(
        max_segments_for_semantic=1000,
        max_semantic_comparisons=50,
        semantic_timeout_seconds=300,
        semantic_batch_size=32,
        semantic_model_name="fake-model",
        semantic_similarity_threshold=0.5,
        repetition_time_window=300,
        max_segments_per_speaker=300,
        cross_speaker_similarity_threshold=0.4,
        cross_speaker_time_window=600,
        max_segments_for_cross_speaker=500,
        use_quality_filtering=True,
        semantic_method="advanced",
        semantic_progress_log_interval_seconds=1,
    )
    for k, v in overrides.items():
        setattr(analysis, k, v)
    return SimpleNamespace(analysis=analysis)


def _patch_model_manager():
    mgr = MagicMock()
    mgr.model = MagicMock()
    mgr.tokenizer = MagicMock()
    mgr.device = "cpu"
    mgr.torch = MagicMock()
    mgr.initialize = MagicMock()
    return patch.object(az, "SemanticModelManager", return_value=mgr)


@pytest.mark.unit
def test_basic_analyzer_init_rejects_str_config() -> None:
    with pytest.raises(TypeError, match="config must be"):
        with _patch_model_manager():
            az.SemanticSimilarityAnalyzer(config="bad")


@pytest.mark.unit
def test_basic_analyzer_calculate_and_tfidf_fallback() -> None:
    with (
        _patch_model_manager(),
        patch.object(az, "get_config", return_value=_cfg(max_semantic_comparisons=2)),
        patch.object(az, "BasicQualityScorer") as scorers,
        patch.object(az, "SemanticSimilarityCalculator") as calc_cls,
    ):
        scorers.return_value = MagicMock()
        calc = MagicMock()
        calc.calculate.return_value = 0.9
        calc.tfidf_similarity.return_value = 0.1
        calc_cls.return_value = calc
        analyzer = az.SemanticSimilarityAnalyzer(
            config=_cfg(max_semantic_comparisons=2)
        )
        assert analyzer.calculate_semantic_similarity("a", "b") == 0.9
        assert analyzer.calculate_semantic_similarity("c", "d") == 0.9
        # third exceeds max_comparisons → tfidf fallback
        assert analyzer.calculate_semantic_similarity("e", "f") == 0.1
        calc.tfidf_similarity.assert_called()


@pytest.mark.unit
def test_basic_analyzer_detect_repetitions_success_path() -> None:
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "We need renewable energy storage today.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "We need renewable energy storage again.",
            "start": 3.0,
            "end": 5.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Renewable energy storage is important.",
            "start": 6.0,
            "end": 8.0,
        },
        {
            "speaker": "SPEAKER_00",
            "text": "ignored label",
            "start": 9.0,
            "end": 10.0,
        },
    ]

    with (
        _patch_model_manager(),
        patch.object(az, "get_config", return_value=_cfg()),
        patch.object(az, "BasicQualityScorer") as scorers,
        patch.object(az, "SemanticSimilarityCalculator") as calc_cls,
        patch.object(
            az,
            "detect_speaker_repetitions_basic",
            return_value=[{"score": 0.9, "type": "self"}],
        ) as det_spk,
        patch.object(
            az,
            "detect_cross_speaker_repetitions_basic",
            return_value=[{"score": 0.8, "type": "cross"}],
        ) as det_cross,
        patch.object(
            az, "cluster_repetitions_basic", return_value=[{"cluster_id": 0}]
        ) as cluster,
        patch.object(
            az,
            "generate_repetition_summary_basic",
            return_value={"total": 2},
        ),
        patch.object(az, "get_text_embedding", return_value=[0.1, 0.2]),
        patch.object(az, "log_progress"),
        patch.object(az, "log_warning"),
        patch.object(az, "log_error"),
    ):
        scorers.return_value.filter_segments.side_effect = lambda segs, n: segs[:n]
        calc_cls.return_value = MagicMock()
        analyzer = az.SemanticSimilarityAnalyzer(config=_cfg())
        result = analyzer.detect_repetitions(segments)
    assert "Alice" in result["speaker_repetitions"]
    assert result["cross_speaker_repetitions"]
    assert result["repetition_clusters"]
    assert result["summary"]["total"] == 2
    det_spk.assert_called()
    det_cross.assert_called()
    cluster.assert_called()


@pytest.mark.unit
def test_basic_analyzer_detect_limits_segments_and_handles_error() -> None:
    segs = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": f"segment number {i} with enough words here",
            "start": float(i),
            "end": float(i) + 1,
        }
        for i in range(5)
    ]
    cfg = _cfg(max_segments_for_semantic=2, use_quality_filtering=False)

    with (
        _patch_model_manager(),
        patch.object(az, "BasicQualityScorer") as scorers,
        patch.object(az, "SemanticSimilarityCalculator"),
        patch.object(az, "log_progress"),
        patch.object(az, "log_warning"),
        patch.object(
            az,
            "detect_speaker_repetitions_basic",
            side_effect=RuntimeError("boom"),
        ),
    ):
        scorers.return_value = MagicMock()
        analyzer = az.SemanticSimilarityAnalyzer(config=cfg)
        result = analyzer.detect_repetitions(segs)
    assert "error" in result["summary"]
    assert result["performance_metrics"].get("error")


@pytest.mark.unit
def test_basic_analyzer_create_visualizations_delegates() -> None:
    with (
        _patch_model_manager(),
        patch.object(az, "BasicQualityScorer"),
        patch.object(az, "SemanticSimilarityCalculator"),
        patch.object(az, "create_visualizations_basic", return_value=["a.png"]) as viz,
    ):
        analyzer = az.SemanticSimilarityAnalyzer(config=_cfg())
        out = analyzer.create_visualizations({"x": 1}, MagicMock(), "base")
    assert out == ["a.png"]
    viz.assert_called_once()


@pytest.mark.unit
def test_advanced_analyzer_detect_and_similarity_fallback() -> None:
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Alpha beta gamma delta epsilon zeta.",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Alpha beta gamma delta epsilon eta.",
            "start": 2.0,
            "end": 3.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Other content about renewable systems.",
            "start": 4.0,
            "end": 5.0,
        },
    ]
    cfg = _cfg(max_semantic_comparisons=1, semantic_method="basic")

    with (
        _patch_model_manager(),
        patch.object(az, "get_config", return_value=cfg),
        patch.object(az, "AdvancedQualityScorer") as scorers,
        patch.object(az, "SemanticSimilarityCalculator") as calc_cls,
        patch.object(
            az,
            "detect_speaker_repetitions_advanced",
            return_value=[{"score": 0.9}],
        ),
        patch.object(
            az,
            "detect_cross_speaker_repetitions_advanced",
            return_value=[],
        ),
        patch.object(az, "cluster_repetitions_advanced", return_value=[]),
        patch.object(
            az, "generate_repetition_summary_advanced", return_value={"ok": True}
        ),
        patch.object(az, "log_info"),
        patch.object(az, "log_warning"),
        patch.object(az, "log_error"),
    ):
        scorers.return_value.filter_segments.side_effect = (
            lambda segs, n, *a, **k: segs[:n]
        )
        calc = MagicMock()
        calc.calculate.return_value = 0.8
        calc.tfidf_similarity.return_value = 0.2
        calc_cls.return_value = calc
        analyzer = az.AdvancedSemanticSimilarityAnalyzer(config=cfg)
        assert analyzer.calculate_semantic_similarity("a", "b") == 0.8
        assert analyzer.calculate_semantic_similarity("c", "d") == 0.2
        result = analyzer.detect_repetitions(segments)
    assert result["summary"]["ok"] is True
    assert "performance_metrics" in result


@pytest.mark.unit
def test_advanced_analyzer_loads_analysis_results_when_advanced() -> None:
    cfg = _cfg(semantic_method="advanced")
    segs = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "One two three four five six.",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    with (
        _patch_model_manager(),
        patch.object(az, "AdvancedQualityScorer") as scorers,
        patch.object(az, "SemanticSimilarityCalculator"),
        patch.object(
            az, "load_analysis_results", return_value={"sentiment": {}}
        ) as load,
        patch.object(az, "detect_speaker_repetitions_advanced", return_value=[]),
        patch.object(az, "detect_cross_speaker_repetitions_advanced", return_value=[]),
        patch.object(az, "cluster_repetitions_advanced", return_value=[]),
        patch.object(az, "generate_repetition_summary_advanced", return_value={}),
        patch.object(az, "log_info"),
        patch.object(az, "log_analysis_error"),
    ):
        scorers.return_value.filter_segments.return_value = segs
        analyzer = az.AdvancedSemanticSimilarityAnalyzer(config=cfg)
        result = analyzer.detect_repetitions(segs, transcript_path="/tmp/t.json")
    load.assert_called_once()
    assert result["analysis_integration"]["integration_successful"] is True


@pytest.mark.unit
def test_advanced_analyzer_error_path_and_viz() -> None:
    cfg = _cfg()
    with (
        _patch_model_manager(),
        patch.object(az, "AdvancedQualityScorer") as scorers,
        patch.object(az, "SemanticSimilarityCalculator"),
        patch.object(
            az,
            "detect_cross_speaker_repetitions_advanced",
            side_effect=RuntimeError("fail"),
        ),
        patch.object(az, "log_info"),
        patch.object(az, "log_analysis_error"),
        patch.object(
            az, "create_visualizations_advanced", return_value=["x.html"]
        ) as viz,
    ):
        scorers.return_value.filter_segments.side_effect = lambda s, n, *a, **k: s[:n]
        analyzer = az.AdvancedSemanticSimilarityAnalyzer(config=cfg)
        bad = analyzer.detect_repetitions(
            [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "x y z a b c",
                    "start": 0,
                    "end": 1,
                }
            ]
        )
        assert "error" in bad
        assert analyzer.create_visualizations({}, MagicMock(), "b") == ["x.html"]
    viz.assert_called_once()


@pytest.mark.unit
def test_advanced_heartbeat_logs_when_interval_elapsed() -> None:
    cfg = _cfg(semantic_progress_log_interval_seconds=1)
    with (
        _patch_model_manager(),
        patch.object(az, "AdvancedQualityScorer"),
        patch.object(az, "SemanticSimilarityCalculator"),
        patch.object(az, "log_info") as log_info,
        patch.object(az.time, "time", return_value=105.0),
    ):
        analyzer = az.AdvancedSemanticSimilarityAnalyzer(config=cfg)
        analyzer._analysis_start_time = 100.0
        analyzer._last_progress_log_time = 100.0
        analyzer._log_progress_heartbeat()
    assert any("Still running" in str(c) for c in log_info.call_args_list)
