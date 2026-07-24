"""Offline unit tests for AffectTensionAnalysis analyze / save / run paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis
from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash
from transcriptx.core.analysis.emotion_family.generational_store import (
    persist_generation,
)


def _seg(speaker: str, **extra):
    base = {
        "speaker": speaker,
        "speaker_db_id": abs(hash(speaker)) % 10000,
        "text": "hello there",
        "start": 0.0,
        "sentiment_compound_norm": -0.4,
        "context_emotion_primary": "joy",
        "context_emotion_scores": {"joy": 0.8, "anger": 0.1, "neutral": 0.1},
    }
    base.update(extra)
    return base


def _usable_contextual_artifact(segments, *, generation_id: str) -> dict:
    return {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": len(segments),
        "artifact_generation_id": generation_id,
        "projection_fields": [
            "segment_id",
            "evaluation_state",
            "analytical_outcome",
            "contextual_emotion_label",
            "contextual_emotion_confidence",
            "truncated",
            "canonical_ref",
        ],
        "segments_with_contextual_emotion": segments,
    }


@pytest.mark.unit
def test_get_dependencies() -> None:
    mod = AffectTensionAnalysis()
    assert "emotion" in mod.get_dependencies()
    assert "sentiment" in mod.get_dependencies()


@pytest.mark.unit
def test_analyze_with_default_thresholds_and_named_speakers(tmp_path) -> None:
    mod = AffectTensionAnalysis()
    text = "hello there"
    text_hash = segment_text_hash(text)
    gid = "d" * 32
    persist_generation(
        tmp_path,
        module_id="contextual_emotion",
        generation_id=gid,
        run_status="complete",
        usable_output=True,
        schema_version="transcriptx.contextual_emotion_result.v1",
        semantics_version="contextual_emotion_v1",
        segments_scored=2,
        canonical_rows=[
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "analytical_outcome": "labeled",
                "scored_text_hash": text_hash,
                "scores": {"joy": 0.8, "anger": 0.1, "neutral": 0.1},
            },
            {
                "segment_id": "s2",
                "evaluation_state": "scored",
                "analytical_outcome": "labeled",
                "scored_text_hash": text_hash,
                "scores": {"joy": 0.7, "anger": 0.2, "neutral": 0.1},
            },
        ],
    )
    segments = [
        _seg(
            "Alice",
            id="s1",
            text=text,
            context_emotion_source="contextual_emotion",
            contextual_emotion_analytical_outcome="labeled",
            contextual_emotion_label="joy",
            contextual_emotion_scored_text_hash=text_hash,
        ),
        _seg(
            "Bob",
            id="s2",
            text=text,
            sentiment_compound_norm=None,
            sentiment={"compound": 0.2},
            context_emotion_source="contextual_emotion",
            contextual_emotion_analytical_outcome="labeled",
            contextual_emotion_label="joy",
            contextual_emotion_scored_text_hash=text_hash,
        ),
        _seg("SPEAKER_00"),
        {"text": "no speaker"},  # excluded
    ]
    artifact = _usable_contextual_artifact(
        [s for s in segments if s.get("id") in {"s1", "s2"}],
        generation_id=gid,
    )
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
    with patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg):
        out = mod.analyze(
            segments,
            contextual_emotion_data=artifact,
            contextual_module_dir=tmp_path,
        )
    assert "derived_indices" in out
    assert out["metadata"]["version"]
    assert "Alice" in out["metadata"]["named_speakers"]
    assert segments[0]["affect_mismatch_posneg"] is not None
    assert "emotion_entropy" in segments[0]
    assert segments[0]["affect_contextual_metrics_status"] == "computed"


@pytest.mark.unit
def test_analyze_with_custom_affect_tension_config() -> None:
    mod = AffectTensionAnalysis()
    at_cfg = SimpleNamespace(
        mismatch_compound_threshold=-0.2,
        trust_like_threshold=0.25,
        pos_emotion_threshold=0.4,
        weight_posneg_mismatch=0.5,
        weight_trust_neutral=0.2,
        weight_entropy=0.2,
        weight_volatility=0.1,
    )
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=at_cfg))
    with patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg):
        out = mod.analyze([_seg("Alice")])
    assert (
        out["metadata"]["params"]["thresholds"]["mismatch_compound_threshold"] == -0.2
    )
    assert out["metadata"]["params"]["weights"]["weight_posneg_mismatch"] == 0.5


@pytest.mark.unit
def test_save_results_writes_payload_and_charts() -> None:
    mod = AffectTensionAnalysis()
    service = MagicMock()
    service.base_name = "mini"
    results = {
        "metadata": {"version": "1.0.0"},
        "derived_indices": {"global": {"score": 1.0}, "by_speaker": {}},
        "segments": [_seg("Alice", affect_mismatch_posneg=True)],
    }
    with (
        patch(
            "transcriptx.core.analysis.affect_tension.output.build_derived_indices_charts",
            return_value=[MagicMock(name="bar")],
        ),
        patch(
            "transcriptx.core.analysis.affect_tension.output.build_dynamics_timeseries_charts",
            return_value=[MagicMock(name="ts")],
        ),
        patch(
            "transcriptx.core.analysis.affect_tension.output.build_tension_summary_heatmap",
            return_value=MagicMock(name="heat"),
        ),
    ):
        mod._save_results(results, service)
    assert service.save_data.call_count >= 2
    assert service.save_chart.call_count >= 1


@pytest.mark.unit
def test_save_results_handles_chart_import_and_build_errors() -> None:
    mod = AffectTensionAnalysis()
    service = MagicMock()
    service.base_name = "mini"
    results = {
        "metadata": {},
        "derived_indices": {},
        "segments": [],
    }
    with (
        patch(
            "transcriptx.core.analysis.affect_tension.output.build_derived_indices_charts",
            side_effect=RuntimeError("bar fail"),
        ),
        patch(
            "transcriptx.core.analysis.affect_tension.output.build_dynamics_timeseries_charts",
            side_effect=RuntimeError("ts fail"),
        ),
        patch(
            "transcriptx.core.analysis.affect_tension.output.build_tension_summary_heatmap",
            side_effect=RuntimeError("heat fail"),
        ),
    ):
        mod._save_results(results, service)
    # json still saved
    assert service.save_data.called


@pytest.mark.unit
def test_run_from_context_empty_and_full(tmp_path) -> None:
    mod = AffectTensionAnalysis()
    service = MagicMock()
    service.base_name = "mini"
    service.get_artifacts.return_value = []

    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = tmp_path
    context.get_run_id.return_value = "r"
    context.get_runtime_flags.return_value = {}
    context.get_segments.return_value = []

    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=service,
        ),
        patch("transcriptx.core.analysis.affect_tension.log_analysis_start"),
        patch("transcriptx.core.analysis.affect_tension.log_analysis_complete"),
    ):
        empty = mod.run_from_context(context)
    assert empty["status"] == "success"
    context.store_analysis_result.assert_called()

    context.get_segments.return_value = [_seg("Alice")]
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=service,
        ),
        patch("transcriptx.core.analysis.affect_tension.log_analysis_start"),
        patch("transcriptx.core.analysis.affect_tension.log_analysis_complete"),
        patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg),
        patch.object(mod, "_save_results") as save,
    ):
        full = mod.run_from_context(context)
    assert full["status"] == "success"
    save.assert_called_once()


@pytest.mark.unit
def test_run_from_context_error_path(tmp_path) -> None:
    mod = AffectTensionAnalysis()
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            side_effect=RuntimeError("boom"),
        ),
        patch("transcriptx.core.analysis.affect_tension.log_analysis_start"),
    ):
        out = mod.run_from_context(context)
    assert out["status"] == "error"
