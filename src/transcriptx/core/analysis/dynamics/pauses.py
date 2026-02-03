"""
Pauses analysis module for TranscriptX.

Detects long pauses and post-question silence events and produces summary stats.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.models.events import Event, generate_event_id
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.validation import sanitize_filename
from transcriptx.io import save_json
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.viz_ids import (
    VIZ_PAUSES_HIST,
    VIZ_PAUSES_TIMELINE,
)
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec

plt = lazy_pyplot()


class PausesAnalysis(AnalysisModule):
    """Analyze silence and timing gaps between segments."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "pauses"
        self.config = get_config().analysis.pauses

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        acts_data: Optional[Dict[str, Any]] = None,
        transcript_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not segments:
            return {
                "events": [],
                "stats": {},
                "speaker_stats": {},
                "gap_series": [],
            }

        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        transcript_hash = transcript_hash or compute_transcript_identity_hash(segments)

        gaps: List[float] = []
        gap_series: List[Dict[str, Any]] = []
        per_segment_pause_count = [0 for _ in segments]
        speaker_gap_stats = defaultdict(list)
        events: List[Event] = []

        # Determine which segments are questions (if acts available)
        question_flags: List[bool] = [False] * len(segments)
        if acts_data:
            acts_segments = acts_data.get("tagged_segments") or acts_data.get("segments")
            if isinstance(acts_segments, list) and len(acts_segments) == len(segments):
                for idx, seg in enumerate(acts_segments):
                    act = (seg or {}).get("dialogue_act", "")
                    if isinstance(act, str) and "question" in act:
                        question_flags[idx] = True

        min_long_pause = float(getattr(self.config, "min_long_pause_seconds", 2.0))
        post_question_multiplier = float(
            getattr(self.config, "post_question_multiplier", 1.5)
        )
        percentile_long_pause = float(
            getattr(self.config, "percentile_long_pause", 0.95)
        )

        for idx in range(len(segments) - 1):
            curr = segments[idx]
            nxt = segments[idx + 1]
            curr_end = curr.get("end")
            nxt_start = nxt.get("start")
            if curr_end is None or nxt_start is None:
                continue
            gap = max(0.0, float(nxt_start) - float(curr_end))
            if gap <= 0:
                continue

            # Speaker resolution
            speaker = None
            curr_info = extract_speaker_info(curr)
            nxt_info = extract_speaker_info(nxt)
            speaker = None
            if curr_info and nxt_info and curr_info.grouping_key == nxt_info.grouping_key:
                speaker = get_speaker_display_name(
                    curr_info.grouping_key, [curr], segments
                )
                if speaker:
                    speaker_gap_stats[speaker].append(gap)

            gaps.append(gap)
            per_segment_pause_count[idx] += 1
            gap_series.append(
                {
                    "segment_idx": idx,
                    "gap_seconds": gap,
                    "time_start": float(curr_end),
                    "time_end": float(nxt_start),
                    "same_speaker": speaker is not None,
                    "speaker": speaker,
                }
            )

        percentiles = {}
        if gaps:
            percentiles = {
                "p90": float(np.percentile(gaps, 90)),
                "p95": float(np.percentile(gaps, 95)),
                "p99": float(np.percentile(gaps, 99)),
            }

        long_pause_threshold = max(
            min_long_pause, percentiles.get("p95", min_long_pause)
        )
        post_question_threshold = min_long_pause * post_question_multiplier

        # Create events
        for entry in gap_series:
            gap = entry["gap_seconds"]
            if gap >= long_pause_threshold:
                event = Event(
                    event_id=generate_event_id(
                        transcript_hash,
                        "long_pause",
                        entry["segment_idx"],
                        entry["segment_idx"] + 1,
                        entry["time_start"],
                        entry["time_end"],
                    ),
                    kind="long_pause",
                    time_start=entry["time_start"],
                    time_end=entry["time_end"],
                    speaker=None if not entry["same_speaker"] else None,
                    segment_start_idx=entry["segment_idx"],
                    segment_end_idx=entry["segment_idx"] + 1,
                    severity=min(1.0, gap / max(long_pause_threshold, 0.1)),
                    evidence=[{"source": "pauses", "feature": "gap_seconds", "value": gap}],
                    links=[
                        {"type": "segment", "idx": entry["segment_idx"]},
                        {"type": "segment", "idx": entry["segment_idx"] + 1},
                    ],
                )
                events.append(event)

            if question_flags[entry["segment_idx"]] and gap >= post_question_threshold:
                event = Event(
                    event_id=generate_event_id(
                        transcript_hash,
                        "post_question_silence",
                        entry["segment_idx"],
                        entry["segment_idx"] + 1,
                        entry["time_start"],
                        entry["time_end"],
                    ),
                    kind="post_question_silence",
                    time_start=entry["time_start"],
                    time_end=entry["time_end"],
                    speaker=None,
                    segment_start_idx=entry["segment_idx"],
                    segment_end_idx=entry["segment_idx"] + 1,
                    severity=min(1.0, gap / max(post_question_threshold, 0.1)),
                    evidence=[
                        {"source": "pauses", "feature": "gap_seconds", "value": gap},
                        {"source": "acts", "feature": "question", "value": True},
                    ],
                    links=[
                        {"type": "segment", "idx": entry["segment_idx"]},
                        {"type": "segment", "idx": entry["segment_idx"] + 1},
                    ],
                )
                events.append(event)

        # Stats
        stats = {
            "total_gaps": len(gaps),
            "mean_gap_seconds": float(np.mean(gaps)) if gaps else 0.0,
            "median_gap_seconds": float(np.median(gaps)) if gaps else 0.0,
            "long_pause_threshold_seconds": float(long_pause_threshold),
            "post_question_threshold_seconds": float(post_question_threshold),
            "percentiles": percentiles,
            "long_pause_count": sum(1 for g in gaps if g >= long_pause_threshold),
            "post_question_silence_count": sum(
                1
                for entry in gap_series
                if question_flags[entry["segment_idx"]]
                and entry["gap_seconds"] >= post_question_threshold
            ),
        }

        speaker_stats: Dict[str, Any] = {}
        for speaker, speaker_gaps in speaker_gap_stats.items():
            if not is_named_speaker(speaker):
                continue
            speaker_stats[speaker] = {
                "gap_count": len(speaker_gaps),
                "mean_gap_seconds": float(np.mean(speaker_gaps))
                if speaker_gaps
                else 0.0,
                "median_gap_seconds": float(np.median(speaker_gaps))
                if speaker_gaps
                else 0.0,
                "long_hesitation_count": sum(
                    1 for g in speaker_gaps if g >= long_pause_threshold
                ),
            }

        return {
            "events": events,
            "stats": stats,
            "speaker_stats": speaker_stats,
            "gap_series": gap_series,
            "per_segment_pause_count": [
                {"segment_idx": idx, "pause_count": count}
                for idx, count in enumerate(per_segment_pause_count)
            ],
        }

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_complete,
                log_analysis_error,
                log_analysis_start,
            )
            from transcriptx.core.output.output_service import create_output_service

            log_analysis_start(self.module_name, context.transcript_path)
            segments = context.get_segments()
            speaker_map = context.get_speaker_map()
            acts_result = context.get_analysis_result("acts")
            results = self.analyze(
                segments,
                speaker_map,
                acts_data=acts_result,
                transcript_hash=context.transcript_key,
            )

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)
            context.store_analysis_result(self.module_name, results)

            log_analysis_complete(self.module_name, context.transcript_path)
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "success",
                "results": results,
                "output_directory": str(
                    output_service.get_output_structure().module_dir
                ),
            }
        except Exception as exc:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(exc),
                "results": {},
            }

    def save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_structure = output_service.get_output_structure()

        events: List[Event] = results.get("events", [])
        stats: Dict[str, Any] = results.get("stats", {})
        speaker_stats: Dict[str, Any] = results.get("speaker_stats", {})
        gap_series: List[Dict[str, Any]] = results.get("gap_series", [])
        per_segment_pause_count: List[Dict[str, Any]] = results.get(
            "per_segment_pause_count", []
        )

        # Ensure output directories exist
        os.makedirs(output_structure.global_data_dir, exist_ok=True)
        os.makedirs(output_structure.speaker_data_dir, exist_ok=True)
        os.makedirs(output_structure.global_charts_dir, exist_ok=True)

        save_events_json(events, output_structure, "pauses.events.json")
        save_json(stats, str(output_structure.global_data_dir / "pauses.stats.json"))
        if per_segment_pause_count:
            save_json(
                per_segment_pause_count,
                str(output_structure.global_data_dir / "pauses.per_segment.json"),
            )

        for speaker, data in speaker_stats.items():
            safe_speaker = sanitize_filename(speaker)
            path = output_structure.speaker_data_dir / f"{safe_speaker}_pauses.stats.json"
            save_json(data, str(path))

        # Charts
        gaps = [entry["gap_seconds"] for entry in gap_series]
        if gaps:
            counts, bin_edges = np.histogram(gaps, bins=20)
            categories = [
                f"{bin_edges[i]:.1f}-{bin_edges[i + 1]:.1f}"
                for i in range(len(counts))
            ]
            spec = BarCategoricalSpec(
                viz_id=VIZ_PAUSES_HIST,
                module=self.module_name,
                name="pauses_hist",
                scope="global",
                chart_intent="bar_categorical",
                title="Pause Duration Distribution",
                x_label="Gap (seconds)",
                y_label="Count",
                categories=categories,
                values=counts.tolist(),
            )
            output_service.save_chart(spec, chart_type="hist")

        events_for_timeline = [e for e in events if e.kind in {"long_pause", "post_question_silence"}]
        if events_for_timeline:
            xs = [e.time_start for e in events_for_timeline]
            ys = [e.time_end - e.time_start for e in events_for_timeline]
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_PAUSES_TIMELINE,
                module=self.module_name,
                name="pauses_timeline",
                scope="global",
                chart_intent="line_timeseries",
                title="Long Pauses Timeline",
                x_label="Time (seconds)",
                y_label="Gap (seconds)",
                markers=True,
                series=[{"name": "Pause", "x": xs, "y": ys}],
            )
            output_service.save_chart(spec, chart_type="timeline")

        # Summary
        output_service.save_summary(stats, speaker_stats, analysis_metadata={})
