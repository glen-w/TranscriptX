"""Offline unit tests for prosody dashboard helpers and run paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from transcriptx.core.analysis.voice import dashboard as dash
from transcriptx.core.analysis.voice.schema import EGEMAPS_CANONICAL_FIELDS


@pytest.mark.unit
def test_safe_speaker_name_and_zscore_scale_hover() -> None:
    assert dash._safe_speaker_name("Alice / Bob") == "Alice___Bob"
    assert dash._safe_speaker_name("A/B") == "A_B"

    empty, mean, std = dash._zscore([])
    assert list(empty) == []
    assert mean == 0.0

    z, mean, std = dash._zscore([1.0, 2.0, 3.0])
    assert abs(mean - 2.0) < 1e-6
    assert std > 0
    assert abs(float(np.mean(z))) < 1e-6

    z0, _, std0 = dash._zscore([5.0, 5.0, 5.0])
    assert std0 == 0.0
    assert list(z0) == [0.0, 0.0, 0.0]

    assert dash._scale_sizes([]) == []
    assert dash._scale_sizes([np.nan, np.nan]) == [6.0, 6.0]
    assert dash._scale_sizes([3.0, 3.0]) == [6.0, 6.0]
    sizes = dash._scale_sizes([1.0, 2.0, 3.0], min_size=6.0, max_size=18.0)
    assert sizes[0] == 6.0
    assert sizes[-1] == 18.0

    hover = dash._build_hover_text(
        {
            "speaker": "Alice",
            "start_s": 1.5,
            "end_s": 2.5,
            "rms_db": -12.0,
            "f0_range_semitones": 3.0,
            "speech_rate_wps": 2.0,
            "voiced_ratio": 0.8,
            "text_snippet": "hello",
        }
    )
    assert "Alice" in hover and "hello" in hover
    hover_na = dash._build_hover_text({"speaker": None})
    assert "n/a" in hover_na


@pytest.mark.unit
def test_resolve_segment_metadata_and_prepare_data(tmp_path) -> None:
    context = MagicMock()
    context.get_transcript_key.return_value = "t"
    context.get_segments.return_value = [
        {
            "speaker": "Alice",
            "start": 0.0,
            "end": 1.0,
            "text": "hello world\nnext",
        }
    ]
    meta = dash.resolve_segment_metadata(context)
    assert "segment_id" in meta.columns
    assert meta.iloc[0]["text_snippet"]

    df = pd.DataFrame(
        [
            {
                "segment_id": "t:0",
                "speaker": "Alice",
                "start_s": 0.0,
                "end_s": 1.0,
                "rms_db": -20.0,
                "f0_mean_hz": 120.0,
                "f0_range_semitones": 4.0,
                "voiced_ratio": 0.7,
                "speech_rate_wps": 2.5,
            }
        ]
    )
    with (
        patch.object(dash, "load_voice_features", return_value=df),
        patch.object(
            dash,
            "resolve_segment_id",
            return_value="t:0",
        ),
    ):
        data = dash._prepare_data(
            context,
            {
                "voice_feature_core_path": str(tmp_path / "core.parquet"),
                "voice_feature_egemaps_path": None,
            },
        )
    assert "duration_s" in data.df.columns
    assert "segment_midpoint_time" in data.df.columns
    assert not data.df_named.empty


@pytest.mark.unit
def test_prepare_data_requires_core_path() -> None:
    with pytest.raises(RuntimeError, match="missing core path"):
        dash._prepare_data(MagicMock(), {})


@pytest.mark.unit
def test_run_from_context_skip_paths(tmp_path) -> None:
    mod = dash.ProsodyDashboardAnalysis()
    assert mod.analyze([]) == {}
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = tmp_path
    context.get_run_id.return_value = "r"
    context.get_runtime_flags.return_value = {}
    service = MagicMock()
    service.get_artifacts.return_value = []

    cfg = SimpleNamespace(
        analysis=SimpleNamespace(voice=SimpleNamespace(egemaps_enabled=True))
    )
    with (
        patch.object(dash, "create_output_service", return_value=service),
        patch.object(dash, "log_analysis_start"),
        patch.object(dash, "log_analysis_complete"),
        patch.object(dash, "get_config", return_value=cfg),
        patch.object(
            dash,
            "check_voice_optional_deps",
            return_value={
                "ok": False,
                "missing_optional_deps": ["opensmile"],
                "install_hint": "pip",
            },
        ),
    ):
        out = mod.run_from_context(context)
    assert out["metrics"]["skipped_reason"] == "missing_optional_deps"

    with (
        patch.object(dash, "create_output_service", return_value=service),
        patch.object(dash, "log_analysis_start"),
        patch.object(dash, "log_analysis_complete"),
        patch.object(dash, "get_config", return_value=cfg),
        patch.object(dash, "check_voice_optional_deps", return_value={"ok": True}),
    ):
        context.get_analysis_result.return_value = {"status": "skipped"}
        out2 = mod.run_from_context(context)
    assert out2["metrics"]["skipped_reason"] == "no_voice_features"


@pytest.mark.unit
def test_run_from_context_success_builds_charts(tmp_path) -> None:
    mod = dash.ProsodyDashboardAnalysis()
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = tmp_path
    context.get_run_id.return_value = "r"
    context.get_runtime_flags.return_value = {}
    context.get_transcript_key.return_value = "t"
    context.get_segments.return_value = [
        {"speaker": "Alice", "start": 0.0, "end": 1.5, "text": "hello"},
        {"speaker": "Bob", "start": 1.5, "end": 3.0, "text": "world"},
    ]
    context.get_analysis_result.return_value = {
        "status": "ok",
        "voice_feature_core_path": str(tmp_path / "core.parquet"),
        "voice_feature_egemaps_path": str(tmp_path / "eg.parquet"),
    }

    rows = []
    for i, spk in enumerate(["Alice", "Alice", "Bob", "Bob"]):
        row = {
            "segment_id": f"t:{i}",
            "speaker": spk,
            "start_s": float(i),
            "end_s": float(i) + 1.5,
            "rms_db": -20.0 + i,
            "f0_mean_hz": 100.0 + i * 5,
            "f0_range_semitones": 2.0 + i * 0.5,
            "voiced_ratio": 0.5 + i * 0.05,
            "speech_rate_wps": 2.0 + i * 0.2,
        }
        for name in list(EGEMAPS_CANONICAL_FIELDS)[:4]:
            row[f"eg_{name}"] = 0.1 * (i + 1)
        rows.append(row)
    # ensure hnr for quality scatter if present in canonical
    if "hnr_db" in EGEMAPS_CANONICAL_FIELDS or any(
        "hnr" in f for f in EGEMAPS_CANONICAL_FIELDS
    ):
        hnr_field = next(f for f in EGEMAPS_CANONICAL_FIELDS if "hnr" in f)
        for r in rows:
            r[f"eg_{hnr_field}"] = 10.0
    else:
        for r in rows:
            r["eg_hnr_db"] = 10.0

    df = pd.DataFrame(rows)
    service = MagicMock()
    service.get_artifacts.return_value = [{"id": "c"}]
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(voice=SimpleNamespace(egemaps_enabled=True))
    )

    with (
        patch.object(dash, "create_output_service", return_value=service),
        patch.object(dash, "log_analysis_start"),
        patch.object(dash, "log_analysis_complete"),
        patch.object(dash, "get_config", return_value=cfg),
        patch.object(dash, "check_voice_optional_deps", return_value={"ok": True}),
        patch.object(dash, "load_voice_features", return_value=df),
        patch.object(
            dash,
            "resolve_segment_id",
            side_effect=lambda seg, key: f"{key}:{context.get_segments().index(seg)}",
        ),
        patch.object(
            dash,
            "build_prosody_overlay_segments_v1_payload",
            return_value={"segments": [{"id": 1}]},
        ),
        patch.object(dash, "time_axis_display", return_value=([0, 1, 2, 3], "Time")),
    ):
        result = mod.run_from_context(context)

    assert result["status"] == "success"
    assert result["metrics"]["prosody.speakers"] >= 1
    assert service.save_chart.call_count >= 3
    assert service.save_summary.called


@pytest.mark.unit
def test_run_from_context_error_path(tmp_path) -> None:
    mod = dash.ProsodyDashboardAnalysis()
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    with (
        patch.object(dash, "create_output_service", side_effect=RuntimeError("boom")),
        patch.object(dash, "log_analysis_start"),
        patch.object(dash, "log_analysis_error"),
    ):
        out = mod.run_from_context(context)
    assert out["status"] == "error"
