from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.audio_io import resolve_audio_path, read_audio_segment
from transcriptx.core.analysis.voice.cache import load_voice_features  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.deps import check_voice_optional_deps
from transcriptx.core.output.output_service import create_output_service  # type: ignore[import-untyped]
from transcriptx.core.utils.logger import (
    get_logger,
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.module_result import build_module_result, now_iso
from transcriptx.core.utils.viz_ids import (
    VIZ_VOICE_F0_CONTOURS_SPEAKER,
    VIZ_VOICE_F0_SLOPE_DISTRIBUTION_GLOBAL,
)
from transcriptx.core.viz.specs import BoxSpec, LineTimeSeriesSpec
from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import-untyped]

logger = get_logger()

MAX_SEGMENTS_PER_SPEAKER = 5
MAX_TOTAL_SECONDS = 180.0
MIN_DURATION_SECONDS = 3.0


def _compute_f0_contour(wave: np.ndarray, sample_rate: int) -> tuple[list[float], list[float]]:
    try:
        import librosa
    except Exception:
        return ([], [])
    hop_length = 256
    try:
        f0 = librosa.yin(
            wave,
            fmin=50.0,
            fmax=500.0,
            sr=sample_rate,
            hop_length=hop_length,
        )
    except Exception:
        return ([], [])
    f0 = np.asarray(f0, dtype=np.float64)
    valid = np.isfinite(f0) & (f0 > 0)
    f0 = f0[valid]
    if f0.size == 0:
        return ([], [])
    times = (np.arange(len(f0)) * hop_length) / float(sample_rate)
    return (times.tolist(), f0.tolist())


def _f0_slope_st_per_s(times: list[float], f0: list[float]) -> float | None:
    if len(times) < 2 or len(f0) < 2:
        return None
    f0_arr = np.asarray(f0, dtype=np.float64)
    t_arr = np.asarray(times, dtype=np.float64)
    valid = (f0_arr > 0) & np.isfinite(f0_arr) & np.isfinite(t_arr)
    if np.sum(valid) < 2:
        return None
    f0_arr = f0_arr[valid]
    t_arr = t_arr[valid]
    # semitone scale relative to 1Hz
    st = 12.0 * np.log2(f0_arr)
    try:
        slope, _ = np.polyfit(t_arr, st, 1)
    except Exception:
        return None
    return float(slope)


class VoiceContoursAnalysis(AnalysisModule):
    """Intonation contour viewer (opt-in)."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "voice_contours"

    def analyze(self, segments: list[dict[str, Any]], speaker_map=None) -> Dict[str, Any]:
        return {}

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        started_at = now_iso()
        try:
            log_analysis_start(self.module_name, context.transcript_path)
            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
                output_namespace="voice",
                output_version="v1",
            )

            deps = check_voice_optional_deps(
                egemaps_enabled=False, required=["librosa", "soundfile"]
            )
            if not deps.get("ok"):
                payload = {
                    "status": "skipped",
                    "skipped_reason": "missing_optional_deps",
                    "missing_optional_deps": deps.get("missing_optional_deps", []),
                    "install_hint": deps.get("install_hint"),
                }
                output_service.save_data(payload, "voice_contours_summary", format_type="json")
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={"skipped_reason": payload["skipped_reason"]},
                    payload_type="analysis_results",
                    payload=payload,
                )

            locator = context.get_analysis_result("voice_features") or {}
            if locator.get("status") != "ok":
                payload = {
                    "status": "skipped",
                    "skipped_reason": locator.get("skipped_reason") or "no_voice_features",
                    "missing_optional_deps": locator.get("missing_optional_deps", []),
                    "install_hint": locator.get("install_hint"),
                }
                output_service.save_data(payload, "voice_contours_summary", format_type="json")
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={"skipped_reason": payload["skipped_reason"]},
                    payload_type="analysis_results",
                    payload=payload,
                )

            core_path = locator.get("voice_feature_core_path")
            eg_path = locator.get("voice_feature_egemaps_path")
            df = load_voice_features(
                core_path=Path(core_path), egemaps_path=Path(eg_path) if eg_path else None
            )

            audio_path = resolve_audio_path(
                transcript_path=context.transcript_path,
                output_dir=context.get_transcript_dir(),
            )
            if not audio_path:
                payload = {"status": "skipped", "skipped_reason": "no_audio"}
                output_service.save_data(payload, "voice_contours_summary", format_type="json")
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    payload_type="analysis_results",
                    payload=payload,
                )

            # Deterministic selection: top N longest voiced segments per speaker
            df = df.copy()
            df = df[df["duration_s"] >= MIN_DURATION_SECONDS]
            selected_rows = []
            total_seconds = 0.0
            for speaker, sub in df.groupby("speaker"):
                if not speaker or not is_named_speaker(str(speaker)):
                    continue
                sub = sub.sort_values("duration_s", ascending=False)
                sub = sub.head(MAX_SEGMENTS_PER_SPEAKER)
                if total_seconds >= MAX_TOTAL_SECONDS:
                    break
                selected_rows.append(sub)
                total_seconds += float(sub["duration_s"].sum())
                if total_seconds >= MAX_TOTAL_SECONDS:
                    break
            if not selected_rows:
                payload = {"status": "skipped", "skipped_reason": "no_segments_selected"}
                output_service.save_data(payload, "voice_contours_summary", format_type="json")
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    payload_type="analysis_results",
                    payload=payload,
                )

            import pandas as pd

            selected_df = pd.concat(selected_rows)
            selected_segment_ids = selected_df["segment_id"].astype(str).tolist()
            summary: dict[str, Any] = {
                "status": "ok",
                "selected_segment_ids": selected_segment_ids,
                "f0_slopes": [],
            }

            slopes_by_speaker: dict[str, list[float]] = {}
            contours_by_speaker: dict[str, list[dict[str, Any]]] = {}
            for _, row in selected_df.iterrows():
                start_s = float(row.get("start_s", 0.0) or 0.0)
                end_s = float(row.get("end_s", start_s) or start_s)
                speaker = str(row.get("speaker") or "")
                if end_s <= start_s:
                    continue
                wave = read_audio_segment(
                    wav_path=audio_path,
                    start_s=start_s,
                    end_s=end_s,
                    sample_rate=16000,
                    pad_s=0.0,
                )
                times, f0 = _compute_f0_contour(wave, 16000)
                if not times or not f0:
                    continue
                slope = _f0_slope_st_per_s(times, f0)
                if slope is not None:
                    slopes_by_speaker.setdefault(speaker, []).append(slope)
                    summary["f0_slopes"].append(
                        {"speaker": speaker, "segment_id": row.get("segment_id"), "slope": slope}
                    )
                contours_by_speaker.setdefault(speaker, []).append(
                    {"name": str(row.get("segment_id")), "x": times, "y": f0}
                )

            for speaker, series in contours_by_speaker.items():
                spec = LineTimeSeriesSpec(
                    viz_id=VIZ_VOICE_F0_CONTOURS_SPEAKER,
                    module=self.module_name,
                    name=f"f0_contours__examples__speaker__{speaker}",
                    scope="speaker",
                    speaker=speaker,
                    chart_intent="line_timeseries",
                    title=f"F0 Contours: {speaker}",
                    x_label="Time (s)",
                    y_label="F0 (Hz)",
                    series=series,
                )
                output_service.save_chart(spec, chart_type="f0_contours")

            # Slope distribution per speaker
            if slopes_by_speaker:
                series = []
                for speaker, slopes in slopes_by_speaker.items():
                    x_vals = [speaker] * len(slopes)
                    series.append({"name": speaker, "x": x_vals, "y": slopes})
                spec = BoxSpec(
                    viz_id=VIZ_VOICE_F0_SLOPE_DISTRIBUTION_GLOBAL,
                    module=self.module_name,
                    name="f0_slope__compare_speakers__all",
                    scope="global",
                    chart_intent="box_plot",
                    title="F0 Slope Distribution (semitones/sec)",
                    x_label="Speaker",
                    y_label="Slope (st/s)",
                    series=series,
                )
                output_service.save_chart(spec, chart_type="f0_slope_distribution")

            output_service.save_data(summary, "voice_contours_summary", format_type="json")
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=output_service.get_artifacts(),
                payload_type="analysis_results",
                payload=summary,
            )
        except Exception as exc:
            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=now_iso(),
                error=str(exc),
            )
