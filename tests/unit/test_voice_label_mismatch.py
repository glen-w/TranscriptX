"""Offline unit tests for VoiceMismatchAnalysis success / error paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from transcriptx.core.analysis.voice_mismatch import VoiceMismatchAnalysis


def _context(tmp_path, locator, segments):
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = tmp_path
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    context.get_analysis_result.return_value = locator
    context.get_segments.return_value = segments
    context.get_transcript_key.return_value = "t"
    return context


def _feature_df():
    return pd.DataFrame(
        [
            {
                "segment_id": "t:0",
                "speaker": "Alice",
                "start_s": 0.0,
                "end_s": 1.0,
                "rms_db": -20.0,
                "f0_range_semitones": 4.0,
                "speech_rate_wps": 2.5,
                "eg_hnr_db": 10.0,
                "eg_jitter": 0.01,
                "eg_shimmer_db": 0.2,
                "eg_alpha_ratio": 1.0,
            },
            {
                "segment_id": "t:1",
                "speaker": "Alice",
                "start_s": 1.0,
                "end_s": 2.0,
                "rms_db": -10.0,
                "f0_range_semitones": 8.0,
                "speech_rate_wps": 3.5,
                "eg_hnr_db": 5.0,
                "eg_jitter": 0.05,
                "eg_shimmer_db": 0.5,
                "eg_alpha_ratio": 0.5,
            },
            {
                "segment_id": "t:2",
                "speaker": "SPEAKER_00",
                "start_s": 2.0,
                "end_s": 3.0,
                "rms_db": -15.0,
                "f0_range_semitones": 3.0,
                "speech_rate_wps": 2.0,
                "eg_hnr_db": 8.0,
                "eg_jitter": 0.02,
                "eg_shimmer_db": 0.3,
                "eg_alpha_ratio": 0.8,
            },
        ]
    )


@pytest.mark.unit
def test_run_from_context_success_with_mocked_features(tmp_path) -> None:
    module = VoiceMismatchAnalysis()
    locator = {
        "status": "ok",
        "voice_feature_core_path": str(tmp_path / "core.parquet"),
        "voice_feature_egemaps_path": str(tmp_path / "eg.parquet"),
    }
    segments = [
        {
            "speaker": "Alice",
            "text": "That is just great.",
            "start": 0.0,
            "end": 1.0,
            "sentiment": {"compound": -0.7},
        },
        {
            "speaker": "Alice",
            "text": "Wonderful news indeed.",
            "start": 1.0,
            "end": 2.0,
            # missing sentiment → score_sentiment path
        },
        {
            "speaker": "SPEAKER_00",
            "text": "um",
            "start": 2.0,
            "end": 3.0,
            "sentiment": {"compound": 0.0},
        },
    ]
    context = _context(tmp_path, locator, segments)
    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = [{"id": "a"}]
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            voice=SimpleNamespace(
                mismatch_threshold=0.0,
                top_k_moments=10,
                include_unnamed_in_global_curves=True,
            )
        )
    )

    with (
        patch(
            "transcriptx.core.analysis.voice_mismatch.create_output_service",
            return_value=fake_service,
        ),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_start"),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_complete"),
        patch(
            "transcriptx.core.analysis.voice_mismatch.load_voice_features",
            return_value=_feature_df(),
        ),
        patch(
            "transcriptx.core.analysis.voice.schema.resolve_segment_id",
            side_effect=lambda seg, key: f"{key}:{segments.index(seg)}",
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.score_sentiment",
            return_value={"compound": 0.2},
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.compute_arousal_raw",
            return_value=0.8,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.compute_valence_proxy",
            return_value=-0.5,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.compute_mismatch_score",
            return_value=0.9,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.mismatch_scatter_spec",
            return_value={"type": "scatter"},
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.mismatch_timeline_spec",
            return_value={"type": "timeline"},
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.robust_stats",
            return_value={"median": 0.0, "iqr": 1.0, "p10": -1.0, "p90": 1.0},
        ),
    ):
        result = module.run_from_context(context)

    assert result["status"] == "success"
    assert result["metrics"]["moments_count"] >= 1
    assert fake_service.save_summary.called
    assert fake_service.save_chart.call_count >= 1


@pytest.mark.unit
def test_run_from_context_missing_core_path_errors(tmp_path) -> None:
    module = VoiceMismatchAnalysis()
    locator = {"status": "ok", "voice_feature_core_path": None}
    context = _context(tmp_path, locator, [])
    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = []
    with (
        patch(
            "transcriptx.core.analysis.voice_mismatch.create_output_service",
            return_value=fake_service,
        ),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_start"),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_error"),
    ):
        result = module.run_from_context(context)
    assert result["status"] == "error"


@pytest.mark.unit
def test_run_from_context_uses_deep_valence_when_present(tmp_path) -> None:
    module = VoiceMismatchAnalysis()
    locator = {
        "status": "ok",
        "voice_feature_core_path": str(tmp_path / "core.parquet"),
    }
    segments = [
        {
            "speaker": "Alice",
            "text": "fine",
            "start": 0.0,
            "end": 1.0,
            "sentiment": {"compound": 0.1},
        }
    ]
    context = _context(tmp_path, locator, segments)
    df = pd.DataFrame(
        [
            {
                "segment_id": "t:0",
                "speaker": "Alice",
                "start_s": 0.0,
                "end_s": 1.0,
                "rms_db": -12.0,
                "f0_range_semitones": 2.0,
                "speech_rate_wps": 2.0,
                "valence_raw": 0.4,
                "deep_emotion_label": "joy",
            }
        ]
    )
    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = []
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            voice=SimpleNamespace(
                mismatch_threshold=0.0,
                top_k_moments=5,
                include_unnamed_in_global_curves=True,
            )
        )
    )
    with (
        patch(
            "transcriptx.core.analysis.voice_mismatch.create_output_service",
            return_value=fake_service,
        ),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_start"),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_complete"),
        patch(
            "transcriptx.core.analysis.voice_mismatch.load_voice_features",
            return_value=df,
        ),
        patch(
            "transcriptx.core.analysis.voice.schema.resolve_segment_id",
            return_value="t:0",
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.compute_arousal_raw",
            return_value=0.3,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.compute_mismatch_score",
            return_value=0.5,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.mismatch_scatter_spec",
            return_value=None,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.mismatch_timeline_spec",
            return_value=None,
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.robust_stats",
            return_value={"median": 0.0, "iqr": 1.0},
        ),
        patch(
            "transcriptx.core.analysis.voice_mismatch.compute_valence_proxy"
        ) as valence_proxy,
    ):
        result = module.run_from_context(context)
    assert result["status"] == "success", result
    valence_proxy.assert_not_called()
    payload = result["payload"]
    assert payload["summary"]["valence_method"] == "deep_model"
