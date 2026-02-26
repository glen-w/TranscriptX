from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.cache import load_voice_features  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.schema import (
    EGEMAPS_CANONICAL_FIELDS,
    resolve_segment_id,
)
from transcriptx.core.analysis.voice.deps import check_voice_optional_deps
from transcriptx.core.output.output_service import create_output_service  # type: ignore[import-untyped]
from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]
from transcriptx.core.utils.lazy_imports import optional_import  # type: ignore[import-untyped]
from transcriptx.core.utils.logger import (  # type: ignore[import-untyped]
    get_logger,
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.module_result import (  # type: ignore[import-untyped]
    build_module_result,
    capture_exception,
    now_iso,
)
from transcriptx.core.utils.viz_ids import (  # type: ignore[import-untyped]
    VIZ_PROSODY_COMPARE_SPEAKERS_GLOBAL,
    VIZ_PROSODY_EGEMAPS_DISTRIBUTION_SPEAKER,
    VIZ_PROSODY_FINGERPRINT_SCATTER_GLOBAL,
    VIZ_PROSODY_PROFILE_CORR_SPEAKER,
    VIZ_PROSODY_PROFILE_DISTRIBUTION_SPEAKER,
    VIZ_PROSODY_QUALITY_SCATTER_GLOBAL,
    VIZ_PROSODY_TIMELINE_GLOBAL,
)
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import (  # type: ignore[import-untyped]
    BoxSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    ScatterSeries,
    ScatterSpec,
)
from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import-untyped]

logger = get_logger()


CORE_FEATURES: tuple[str, ...] = (
    "rms_db",
    "f0_mean_hz",
    "f0_range_semitones",
    "voiced_ratio",
    "speech_rate_wps",
)

HEADLINE_FEATURES: tuple[str, ...] = (
    "rms_db",
    "f0_range_semitones",
    "speech_rate_wps",
)


def _safe_speaker_name(speaker: str) -> str:
    return str(speaker).replace(" ", "_").replace("/", "_")


def resolve_segment_metadata(context: Any):  # -> pandas.DataFrame
    pd = optional_import("pandas", "prosody dashboard segment metadata")
    transcript_key = context.get_transcript_key()
    rows: list[dict[str, Any]] = []
    for seg in context.get_segments() or []:
        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", start) or start)
        duration = float(end - start)
        speaker = seg.get("speaker")
        text = (seg.get("text") or "").strip().replace("\n", " ")
        snippet = text[:200]
        seg_id = resolve_segment_id(seg, transcript_key)
        rows.append(
            {
                "segment_id": seg_id,
                "start_s": start,
                "end_s": end,
                "duration_s": duration,
                "speaker": speaker,
                "text_snippet": snippet,
            }
        )
    return pd.DataFrame(rows)


def _zscore(values: Iterable[float]) -> tuple[np.ndarray, float, float]:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0 or not np.any(np.isfinite(arr)):
        return arr, 0.0, 0.0
    mean = float(np.nanmean(arr))
    std = float(np.nanstd(arr))
    if std <= 0 or not np.isfinite(std):
        return np.zeros_like(arr), mean, std
    return (arr - mean) / std, mean, std


def _scale_sizes(
    values: Iterable[float], min_size: float = 6.0, max_size: float = 18.0
) -> list[float]:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0 or not np.any(np.isfinite(arr)):
        return [] if arr.size == 0 else [float(min_size) for _ in arr]
    vmin = float(np.nanmin(arr))
    vmax = float(np.nanmax(arr))
    if vmax <= vmin:
        return [float(min_size) for _ in arr]
    scaled = min_size + (arr - vmin) * (max_size - min_size) / (vmax - vmin)
    return [float(x) for x in scaled]


def _build_hover_text(row: Any) -> str:
    speaker = row.get("speaker") or ""
    start_s = row.get("start_s")
    end_s = row.get("end_s")
    snippet = row.get("text_snippet") or ""
    fields = [
        f"speaker: {speaker}",
        (
            f"start_s: {start_s:.2f}"
            if isinstance(start_s, (int, float))
            else "start_s: n/a"
        ),
        f"end_s: {end_s:.2f}" if isinstance(end_s, (int, float)) else "end_s: n/a",
        (
            f"rms_db: {row.get('rms_db'):.2f}"
            if isinstance(row.get("rms_db"), (int, float))
            else "rms_db: n/a"
        ),
        (
            f"f0_range_semitones: {row.get('f0_range_semitones'):.2f}"
            if isinstance(row.get("f0_range_semitones"), (int, float))
            else "f0_range_semitones: n/a"
        ),
        (
            f"speech_rate_wps: {row.get('speech_rate_wps'):.2f}"
            if isinstance(row.get("speech_rate_wps"), (int, float))
            else "speech_rate_wps: n/a"
        ),
        (
            f"voiced_ratio: {row.get('voiced_ratio'):.2f}"
            if isinstance(row.get("voiced_ratio"), (int, float))
            else "voiced_ratio: n/a"
        ),
    ]
    if snippet:
        fields.append(f"text: {snippet}")
    return "\n".join(fields)


@dataclass
class _ProsodyData:
    df: Any
    df_named: Any
    df_hover: Any


def _prepare_data(context: Any, locator: Dict[str, Any]) -> _ProsodyData:
    pd = optional_import("pandas", "prosody dashboard")
    core_path = locator.get("voice_feature_core_path")
    if not core_path:
        raise RuntimeError("voice_features locator missing core path")
    eg_path = locator.get("voice_feature_egemaps_path")
    df = load_voice_features(
        core_path=__import__("pathlib").Path(core_path),
        egemaps_path=__import__("pathlib").Path(eg_path) if eg_path else None,
    )
    if "duration_s" not in df.columns and {"start_s", "end_s"} <= set(df.columns):
        df = df.assign(
            duration_s=df["end_s"].astype(float) - df["start_s"].astype(float)
        )
    if "segment_midpoint_time" not in df.columns and {"start_s", "end_s"} <= set(
        df.columns
    ):
        df = df.assign(
            segment_midpoint_time=(
                df["start_s"].astype(float) + df["end_s"].astype(float)
            )
            / 2.0
        )

    segment_meta = resolve_segment_metadata(context)
    if "segment_id" in df.columns and "segment_id" in segment_meta.columns:
        df_hover = df.merge(
            segment_meta[["segment_id", "text_snippet"]], on="segment_id", how="left"
        )
    else:
        df_hover = df.copy()
        df_hover["text_snippet"] = None

    df_named = df[df["speaker"].apply(lambda s: bool(s) and is_named_speaker(str(s)))]
    return _ProsodyData(df=df, df_named=df_named, df_hover=df_hover)


class ProsodyDashboardAnalysis(AnalysisModule):
    """Prosody dashboard charts from voice features."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "prosody_dashboard"

    def analyze(self, segments, speaker_map=None) -> Dict[str, Any]:
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
            )

            voice_cfg = getattr(getattr(get_config(), "analysis", None), "voice", None)
            egemaps_enabled = bool(getattr(voice_cfg, "egemaps_enabled", True))
            deps = check_voice_optional_deps(egemaps_enabled=egemaps_enabled)
            if not deps.get("ok"):
                payload = {
                    "status": "skipped",
                    "skipped_reason": "missing_optional_deps",
                    "missing_optional_deps": deps.get("missing_optional_deps", []),
                    "install_hint": deps.get("install_hint"),
                }
                output_service.save_data(
                    payload, "prosody_dashboard_locator", format_type="json"
                )
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={
                        "skipped_reason": payload["skipped_reason"],
                        "missing_optional_deps": payload["missing_optional_deps"],
                    },
                    payload_type="analysis_results",
                    payload=payload,
                )

            locator = context.get_analysis_result("voice_features") or {}
            if locator.get("status") != "ok":
                skipped_reason = locator.get("skipped_reason") or "no_voice_features"
                payload = {
                    "status": "skipped",
                    "skipped_reason": skipped_reason,
                    "missing_optional_deps": locator.get("missing_optional_deps", []),
                    "install_hint": locator.get("install_hint"),
                }
                output_service.save_data(
                    payload, "prosody_dashboard_locator", format_type="json"
                )
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={"skipped_reason": skipped_reason},
                    payload_type="analysis_results",
                    payload=payload,
                )

            data = _prepare_data(context, locator)
            df = data.df
            df_named = data.df_named
            df_hover = data.df_hover

            # Per-speaker distributions and correlations
            for speaker in sorted({str(s) for s in df_named["speaker"].dropna()}):
                speaker_df = df_named[df_named["speaker"].astype(str) == speaker]
                if speaker_df.empty:
                    continue
                safe_speaker = _safe_speaker_name(speaker)

                # Distribution (BoxSpec)
                x_vals: list[str] = []
                y_vals: list[float] = []
                for feature in CORE_FEATURES:
                    if feature not in speaker_df.columns:
                        continue
                    vals = speaker_df[feature].dropna().astype(float).tolist()
                    x_vals.extend([feature] * len(vals))
                    y_vals.extend(vals)
                if y_vals:
                    spec_dist = BoxSpec(
                        viz_id=VIZ_PROSODY_PROFILE_DISTRIBUTION_SPEAKER,
                        module=self.module_name,
                        name=f"prosody_profile_distribution__speaker__{safe_speaker}",
                        scope="speaker",
                        speaker=speaker,
                        chart_intent="box_plot",
                        title=f"Prosody Profile Distribution: {speaker}",
                        x_label="Feature",
                        y_label="Value",
                        show_points=True,
                        series=[{"name": "features", "x": x_vals, "y": y_vals}],
                    )
                    output_service.save_chart(spec_dist, chart_type="prosody_dashboard")

                # Correlation heatmap
                if "duration_s" in speaker_df.columns:
                    filtered = speaker_df[speaker_df["duration_s"].astype(float) >= 1.0]
                else:
                    filtered = speaker_df
                corr_df = (
                    filtered[list(f for f in CORE_FEATURES if f in filtered.columns)]
                    .astype(float)
                    .dropna()
                    .corr()
                )
                if not corr_df.empty:
                    spec_corr = HeatmapMatrixSpec(
                        viz_id=VIZ_PROSODY_PROFILE_CORR_SPEAKER,
                        module=self.module_name,
                        name=f"prosody_profile_corr__speaker__{safe_speaker}",
                        scope="speaker",
                        speaker=speaker,
                        chart_intent="heatmap_matrix",
                        title=f"Prosody Feature Correlations: {speaker} (n={len(filtered)})",
                        x_label="Feature",
                        y_label="Feature",
                        z=corr_df.values.tolist(),
                        x_labels=list(corr_df.columns),
                        y_labels=list(corr_df.index),
                    )
                    output_service.save_chart(spec_corr, chart_type="prosody_dashboard")

            # Timeline (global z-scored)
            timeline_df = df_hover.copy()
            if "segment_midpoint_time" in timeline_df.columns:
                timeline_df = timeline_df.sort_values("segment_midpoint_time")
            x_times = timeline_df["segment_midpoint_time"].astype(float).tolist()
            x_display, timeline_x_label = time_axis_display(x_times)
            series: list[dict[str, Any]] = []
            for feature in CORE_FEATURES:
                if feature not in timeline_df.columns:
                    continue
                values = timeline_df[feature].astype(float).to_numpy()
                z_vals, _, std = _zscore(values)
                if std <= 0:
                    continue
                series.append(
                    {
                        "name": feature,
                        "x": x_display,
                        "y": z_vals.tolist(),
                        "text": (
                            [
                                _build_hover_text(row)
                                for _, row in timeline_df.iterrows()
                            ]
                            if "text_snippet" in timeline_df.columns
                            else None
                        ),
                    }
                )
            if series:
                spec_timeline = LineTimeSeriesSpec(
                    viz_id=VIZ_PROSODY_TIMELINE_GLOBAL,
                    module=self.module_name,
                    name="prosody_timeline__global__all",
                    scope="global",
                    chart_intent="line_timeseries",
                    title="Prosody Timeline (z-scored, global)",
                    x_label=timeline_x_label,
                    y_label="Z-score",
                    markers=False,
                    series=series,
                )
                output_service.save_chart(spec_timeline, chart_type="prosody_dashboard")

            # Speaker comparison (headline features)
            compare_series: list[dict[str, Any]] = []
            for feature in HEADLINE_FEATURES:
                if feature not in df_named.columns:
                    continue
                x_vals = []
                y_vals = []
                for speaker in sorted({str(s) for s in df_named["speaker"].dropna()}):
                    vals = (
                        df_named[df_named["speaker"].astype(str) == speaker][feature]
                        .dropna()
                        .astype(float)
                        .tolist()
                    )
                    x_vals.extend([speaker] * len(vals))
                    y_vals.extend(vals)
                if y_vals:
                    compare_series.append({"name": feature, "x": x_vals, "y": y_vals})
            if compare_series:
                spec_compare = BoxSpec(
                    viz_id=VIZ_PROSODY_COMPARE_SPEAKERS_GLOBAL,
                    module=self.module_name,
                    name="compare_speakers__core_features__all",
                    scope="global",
                    chart_intent="box_plot",
                    title="Speaker Comparison (headline features)",
                    x_label="Speaker",
                    y_label="Value",
                    show_points=False,
                    series=compare_series,
                )
                output_service.save_chart(spec_compare, chart_type="prosody_dashboard")

            # Fingerprint scatter
            scatter_series: list[ScatterSeries] = []
            for speaker in sorted({str(s) for s in df_named["speaker"].dropna()}):
                speaker_df = df_hover[df_hover["speaker"].astype(str) == speaker]
                if speaker_df.empty:
                    continue
                sizes = _scale_sizes(speaker_df.get("speech_rate_wps", []))
                scatter_series.append(
                    ScatterSeries(
                        name=speaker,
                        x=speaker_df["f0_range_semitones"].astype(float).tolist(),
                        y=speaker_df["rms_db"].astype(float).tolist(),
                        text=[_build_hover_text(r) for _, r in speaker_df.iterrows()],
                        marker={"opacity": 0.6, "size": sizes},
                    )
                )
            if scatter_series:
                spec_scatter = ScatterSpec(
                    viz_id=VIZ_PROSODY_FINGERPRINT_SCATTER_GLOBAL,
                    module=self.module_name,
                    name="fingerprint_scatter__global__all",
                    scope="global",
                    chart_intent="scatter",
                    title="Prosody Fingerprint Scatter",
                    x_label="F0 range (semitones)",
                    y_label="RMS (dB)",
                    series=scatter_series,
                    mode="markers",
                )
                output_service.save_chart(spec_scatter, chart_type="prosody_dashboard")

            # eGeMAPS panels (optional)
            cfg = get_config()
            voice_cfg = getattr(getattr(cfg, "analysis", None), "voice", None)
            if bool(getattr(voice_cfg, "egemaps_enabled", True)):
                eg_columns = [
                    f"eg_{name}"
                    for name in EGEMAPS_CANONICAL_FIELDS
                    if f"eg_{name}" in df.columns
                ]
                missing = [
                    name
                    for name in EGEMAPS_CANONICAL_FIELDS
                    if f"eg_{name}" not in df.columns
                ]
                if missing:
                    logger.warning(f"[PROSODY] Missing eGeMAPS columns: {missing}")
                if eg_columns:
                    for speaker in sorted(
                        {str(s) for s in df_named["speaker"].dropna()}
                    ):
                        speaker_df = df_named[
                            df_named["speaker"].astype(str) == speaker
                        ]
                        if speaker_df.empty:
                            continue
                        safe_speaker = _safe_speaker_name(speaker)
                        x_vals: list[str] = []
                        y_vals: list[float] = []
                        for name in EGEMAPS_CANONICAL_FIELDS:
                            col = f"eg_{name}"
                            if col not in speaker_df.columns:
                                continue
                            vals = speaker_df[col].dropna().astype(float).tolist()
                            x_vals.extend([name] * len(vals))
                            y_vals.extend(vals)
                        if y_vals:
                            spec_eg_dist = BoxSpec(
                                viz_id=VIZ_PROSODY_EGEMAPS_DISTRIBUTION_SPEAKER,
                                module=self.module_name,
                                name=f"egemaps_profile_distribution__speaker__{safe_speaker}",
                                scope="speaker",
                                speaker=speaker,
                                chart_intent="box_plot",
                                title=f"eGeMAPS Profile Distribution: {speaker}",
                                x_label="Feature",
                                y_label="Value",
                                show_points=True,
                                series=[{"name": "egemaps", "x": x_vals, "y": y_vals}],
                            )
                            output_service.save_chart(
                                spec_eg_dist, chart_type="prosody_dashboard"
                            )

                    # Quality scatter (hnr_db vs rms_db)
                    if "eg_hnr_db" in df_hover.columns and "rms_db" in df_hover.columns:
                        scatter_series = []
                        for speaker in sorted(
                            {str(s) for s in df_named["speaker"].dropna()}
                        ):
                            speaker_df = df_hover[
                                df_hover["speaker"].astype(str) == speaker
                            ]
                            if speaker_df.empty:
                                continue
                            scatter_series.append(
                                ScatterSeries(
                                    name=speaker,
                                    x=speaker_df["eg_hnr_db"].astype(float).tolist(),
                                    y=speaker_df["rms_db"].astype(float).tolist(),
                                    text=[
                                        _build_hover_text(r)
                                        for _, r in speaker_df.iterrows()
                                    ],
                                    marker={"opacity": 0.6, "size": 8},
                                )
                            )
                        if scatter_series:
                            spec_quality = ScatterSpec(
                                viz_id=VIZ_PROSODY_QUALITY_SCATTER_GLOBAL,
                                module=self.module_name,
                                name="quality_scatter__global__all",
                                scope="global",
                                chart_intent="scatter",
                                title="Voice Quality vs Energy",
                                x_label="HNR (dB)",
                                y_label="RMS (dB)",
                                series=scatter_series,
                                mode="markers",
                            )
                            output_service.save_chart(
                                spec_quality, chart_type="prosody_dashboard"
                            )

            summary = {
                "speakers": len({str(s) for s in df_named["speaker"].dropna()}),
                "segments": int(len(df)),
            }
            output_service.save_summary(summary, {}, analysis_metadata={})

            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=output_service.get_artifacts(),
                metrics=summary,
                payload_type="analysis_results",
                payload={},
            )
        except Exception as exc:
            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=[],
                metrics={},
                payload_type="analysis_results",
                payload={},
                error=capture_exception(exc),
            )
