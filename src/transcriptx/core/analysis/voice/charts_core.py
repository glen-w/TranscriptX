from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.cache import load_voice_features  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.rhythm import npvi, varco
from transcriptx.core.output.output_service import create_output_service  # type: ignore[import-untyped]
from transcriptx.core.utils.logger import (
    get_logger,
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.module_result import build_module_result, now_iso
from transcriptx.core.utils.viz_ids import (
    VIZ_VOICE_BURSTINESS_SPEAKER,
    VIZ_VOICE_HESITATION_MAP_GLOBAL,
    VIZ_VOICE_PAUSES_DISTRIBUTION_GLOBAL,
    VIZ_VOICE_PAUSES_DISTRIBUTION_SPEAKER,
    VIZ_VOICE_PAUSES_TIMELINE_GLOBAL,
    VIZ_VOICE_RHYTHM_COMPARE_GLOBAL,
    VIZ_VOICE_RHYTHM_SCATTER_GLOBAL,
)
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    LineTimeSeriesSpec,
    ScatterSeries,
    ScatterSpec,
)
from transcriptx.core.utils.validation import sanitize_filename
from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import-untyped]

logger = get_logger()

MAX_SEGMENTS_PER_SPEAKER = 200
MAX_TOTAL_SEGMENTS = 2000


def _load_vad_runs(path: str | None) -> dict[str, dict[str, list[float]]]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


@dataclass
class SpeakerRhythm:
    speaker: str
    nPVI_voiced: float | None
    nPVI_silence: float | None
    varco_voiced: float | None
    varco_silence: float | None


class VoiceChartsCoreAnalysis(AnalysisModule):
    """Voice charts core: pauses + rhythm indices."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "voice_charts_core"

    def analyze(
        self, segments: list[dict[str, Any]], speaker_map=None
    ) -> Dict[str, Any]:
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

            locator = context.get_analysis_result("voice_features") or {}
            if locator.get("status") != "ok":
                payload = {
                    "status": "skipped",
                    "skipped_reason": locator.get("skipped_reason")
                    or "no_voice_features",
                    "missing_optional_deps": locator.get("missing_optional_deps", []),
                    "install_hint": locator.get("install_hint"),
                }
                output_service.save_data(
                    payload, "voice_charts_core_summary", format_type="json"
                )
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
                core_path=Path(core_path),
                egemaps_path=Path(eg_path) if eg_path else None,
            )
            vad_runs = _load_vad_runs(locator.get("voice_feature_vad_runs_path"))

            pauses = context.get_analysis_result("pauses") or {}
            gap_series = pauses.get("gap_series") or []
            per_segment_pause = pauses.get("per_segment_pause_count") or []

            summary: dict[str, Any] = {
                "status": "ok",
                "pause_counts": per_segment_pause,
                "rhythm_indices": [],
                "burstiness": [],
                "sampled_segments": [],
            }

            # Pause distribution (global + per speaker)
            gaps = [
                entry["gap_seconds"] for entry in gap_series if "gap_seconds" in entry
            ]
            if gaps:
                counts, bin_edges = np.histogram(gaps, bins=20)
                categories = [
                    f"{bin_edges[i]:.1f}-{bin_edges[i + 1]:.1f}"
                    for i in range(len(counts))
                ]
                spec = BarCategoricalSpec(
                    viz_id=VIZ_VOICE_PAUSES_DISTRIBUTION_GLOBAL,
                    module=self.module_name,
                    name="pauses_distribution__global__all",
                    scope="global",
                    chart_intent="bar_categorical",
                    title="Pause Duration Distribution",
                    x_label="Gap (seconds)",
                    y_label="Count",
                    categories=categories,
                    values=counts.tolist(),
                )
                output_service.save_chart(spec, chart_type="pauses_distribution")

                # Per speaker distribution if we have speaker info
                by_speaker: dict[str, list[float]] = {}
                for entry in gap_series:
                    speaker = entry.get("speaker")
                    if not speaker or not is_named_speaker(speaker):
                        continue
                    by_speaker.setdefault(str(speaker), []).append(
                        entry.get("gap_seconds", 0.0)
                    )
                for speaker, gaps_s in by_speaker.items():
                    counts_s, bin_edges_s = np.histogram(gaps_s, bins=20)
                    categories_s = [
                        f"{bin_edges_s[i]:.1f}-{bin_edges_s[i + 1]:.1f}"
                        for i in range(len(counts_s))
                    ]
                    spec_s = BarCategoricalSpec(
                        viz_id=VIZ_VOICE_PAUSES_DISTRIBUTION_SPEAKER,
                        module=self.module_name,
                        name=f"pauses_distribution__speaker__{sanitize_filename(speaker)}",
                        scope="speaker",
                        speaker=speaker,
                        chart_intent="bar_categorical",
                        title=f"Pause Duration Distribution: {speaker}",
                        x_label="Gap (seconds)",
                        y_label="Count",
                        categories=categories_s,
                        values=counts_s.tolist(),
                    )
                    output_service.save_chart(spec_s, chart_type="pauses_distribution")

            # Pause timeline
            if gap_series:
                valid = [
                    (float(e["time_start"]), e["gap_seconds"])
                    for e in gap_series
                    if e.get("time_start") is not None
                    and e.get("gap_seconds") is not None
                ]
                if valid:
                    xs = [t for t, _ in valid]
                    ys = [g for _, g in valid]
                    x_display, x_label = time_axis_display(xs)
                    spec = LineTimeSeriesSpec(
                        viz_id=VIZ_VOICE_PAUSES_TIMELINE_GLOBAL,
                        module=self.module_name,
                        name="pauses_timeline__global__all",
                        scope="global",
                        chart_intent="line_timeseries",
                        title="Pause Timeline",
                        x_label=x_label,
                        y_label="Gap (seconds)",
                        markers=True,
                        series=[{"name": "Pause", "x": x_display, "y": ys}],
                    )
                    output_service.save_chart(spec, chart_type="pauses_timeline")

            # Hesitation map (pause_count vs speech_rate_wps)
            if per_segment_pause and "segment_idx" in df.columns:
                pause_map = {
                    p["segment_idx"]: p["pause_count"] for p in per_segment_pause
                }
                df_filtered = df.copy()
                df_filtered["pause_count"] = df_filtered["segment_idx"].map(pause_map)
                df_filtered = df_filtered.dropna(
                    subset=["pause_count", "speech_rate_wps"]
                )
                if not df_filtered.empty:
                    # Cap by speaker and total (deterministic: lowest segment_idx)
                    df_filtered = df_filtered.sort_values("segment_idx")
                    sampled_rows = []
                    total = 0
                    for speaker, sub in df_filtered.groupby("speaker"):
                        if total >= MAX_TOTAL_SEGMENTS:
                            break
                        sub = sub.head(MAX_SEGMENTS_PER_SPEAKER)
                        sampled_rows.append(sub)
                        total += len(sub)
                    df_sampled = (
                        df_filtered if not sampled_rows else pd.concat(sampled_rows)
                    )
                    summary["sampled_segments"] = df_sampled["segment_id"].tolist()
                    series = [
                        ScatterSeries(
                            name="Hesitation",
                            x=df_sampled["speech_rate_wps"].tolist(),
                            y=df_sampled["pause_count"].tolist(),
                            text=df_sampled["speaker"].astype(str).tolist(),
                        )
                    ]
                    spec = ScatterSpec(
                        viz_id=VIZ_VOICE_HESITATION_MAP_GLOBAL,
                        module=self.module_name,
                        name="hesitation_map__global__all",
                        scope="global",
                        chart_intent="scatter",
                        title="Hesitation Map (Pause Count vs Speech Rate)",
                        x_label="Speech rate (wps)",
                        y_label="Pause count",
                        series=series,
                    )
                    output_service.save_chart(spec, chart_type="hesitation_map")

            # Burstiness (voiced run lengths per speaker)
            by_speaker_runs: dict[str, list[float]] = {}
            by_speaker_duration: dict[str, float] = {}
            if vad_runs:
                for _, row in df.iterrows():
                    speaker = row.get("speaker")
                    seg_id = str(row.get("segment_id"))
                    if not speaker or not is_named_speaker(str(speaker)):
                        continue
                    runs = vad_runs.get(seg_id, {}).get("voiced_runs_s", [])
                    if not runs:
                        continue
                    by_speaker_runs.setdefault(str(speaker), []).extend(runs)
                    by_speaker_duration[str(speaker)] = by_speaker_duration.get(
                        str(speaker), 0.0
                    ) + float(row.get("duration_s", 0.0) or 0.0)

                for speaker, runs in by_speaker_runs.items():
                    if not runs:
                        continue
                    bursts_per_min = None
                    duration = by_speaker_duration.get(speaker, 0.0)
                    if duration > 0:
                        bursts_per_min = float(len(runs) / (duration / 60.0))
                    summary["burstiness"].append(
                        {
                            "speaker": speaker,
                            "bursts_per_minute": bursts_per_min,
                            "voiced_run_count": len(runs),
                        }
                    )
                    x_vals = ["voiced_runs"] * len(runs)
                    spec = BoxSpec(
                        viz_id=VIZ_VOICE_BURSTINESS_SPEAKER,
                        module=self.module_name,
                        name=f"burstiness__speaker__{sanitize_filename(speaker)}",
                        scope="speaker",
                        speaker=speaker,
                        chart_intent="box_plot",
                        title=f"Burstiness (Voiced Run Lengths): {speaker}",
                        x_label="Run type",
                        y_label="Run length (s)",
                        series=[{"name": "voiced_runs", "x": x_vals, "y": runs}],
                    )
                    output_service.save_chart(spec, chart_type="burstiness")

            # Rhythm indices
            rhythm_rows: list[SpeakerRhythm] = []
            if vad_runs:
                for speaker, runs in by_speaker_runs.items():
                    silence_runs: list[float] = []
                    # collect silence runs for this speaker
                    for _, row in df.iterrows():
                        if str(row.get("speaker")) != speaker:
                            continue
                        seg_id = str(row.get("segment_id"))
                        silence_runs.extend(
                            vad_runs.get(seg_id, {}).get("silence_runs_s", [])
                        )
                    rhythm_rows.append(
                        SpeakerRhythm(
                            speaker=speaker,
                            nPVI_voiced=npvi(runs),
                            nPVI_silence=npvi(silence_runs),
                            varco_voiced=varco(runs),
                            varco_silence=varco(silence_runs),
                        )
                    )
            summary["rhythm_indices"] = [r.__dict__ for r in rhythm_rows]

            if rhythm_rows:
                categories = [r.speaker for r in rhythm_rows]
                series = [
                    {
                        "name": "nPVI_voiced",
                        "categories": categories,
                        "values": [r.nPVI_voiced or 0.0 for r in rhythm_rows],
                    },
                    {
                        "name": "nPVI_silence",
                        "categories": categories,
                        "values": [r.nPVI_silence or 0.0 for r in rhythm_rows],
                    },
                    {
                        "name": "varco_voiced",
                        "categories": categories,
                        "values": [r.varco_voiced or 0.0 for r in rhythm_rows],
                    },
                    {
                        "name": "varco_silence",
                        "categories": categories,
                        "values": [r.varco_silence or 0.0 for r in rhythm_rows],
                    },
                ]
                spec = BarCategoricalSpec(
                    viz_id=VIZ_VOICE_RHYTHM_COMPARE_GLOBAL,
                    module=self.module_name,
                    name="rhythm_compare__global__all",
                    scope="global",
                    chart_intent="bar_categorical",
                    title="Rhythm Indices by Speaker",
                    x_label="Speaker",
                    y_label="Index value",
                    series=series,
                )
                output_service.save_chart(spec, chart_type="rhythm_compare")

                # Rhythm scatter vs speech_rate_wps
                if "speech_rate_wps" in df.columns and "voiced_ratio" in df.columns:
                    series = []
                    for r in rhythm_rows:
                        speaker_df = df[df["speaker"] == r.speaker]
                        if speaker_df.empty:
                            continue
                        x = speaker_df["speech_rate_wps"].dropna().tolist()
                        y = [r.nPVI_voiced] * len(x)
                        if x and r.nPVI_voiced is not None:
                            series.append(
                                ScatterSeries(
                                    name=r.speaker,
                                    x=x,
                                    y=y,
                                )
                            )
                    if series:
                        spec = ScatterSpec(
                            viz_id=VIZ_VOICE_RHYTHM_SCATTER_GLOBAL,
                            module=self.module_name,
                            name="rhythm_scatter__global__all",
                            scope="global",
                            chart_intent="scatter",
                            title="Rhythm vs Speech Rate",
                            x_label="Speech rate (wps)",
                            y_label="nPVI (voiced)",
                            series=series,
                        )
                        output_service.save_chart(spec, chart_type="rhythm_scatter")

            output_service.save_data(
                summary, "voice_charts_core_summary", format_type="json"
            )
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
