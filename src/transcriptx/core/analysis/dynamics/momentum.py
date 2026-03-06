"""
Momentum analysis module for TranscriptX.

Computes a stall/flow index across time windows and detects stall zones and cliffs.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.models.events import Event, generate_event_id
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.io import save_csv, save_json
from transcriptx.core.utils.viz_ids import VIZ_MOMENTUM_TIMESERIES
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import LineTimeSeriesSpec

plt = lazy_pyplot()


class MomentumAnalysis(AnalysisModule):
    """Compute momentum score and stall/flow events."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "momentum"
        self.config = get_config().analysis.momentum

    def _tokenize(self, text: str) -> List[str]:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

        tokens = re.findall(r"\b\w+\b", text.lower())
        return [tok for tok in tokens if tok not in ENGLISH_STOP_WORDS and len(tok) > 2]

    def _window_segments(
        self, segments: List[Dict[str, Any]], start: float, end: float
    ) -> List[Dict[str, Any]]:
        return [
            seg
            for seg in segments
            if seg.get("start", 0.0) >= start and seg.get("start", 0.0) < end
        ]

    def _calculate_turn_energy(self, window_segments: List[Dict[str, Any]]) -> float:
        if not window_segments:
            return 0.0
        speakers = [seg.get("speaker") for seg in window_segments]
        alternations = sum(
            1 for i in range(1, len(speakers)) if speakers[i] != speakers[i - 1]
        )
        turns = len(window_segments)
        # Normalize to 0-1 with a soft cap
        turn_energy = min(1.0, (turns + alternations) / max(turns * 2, 1))
        return float(turn_energy)

    def _calculate_novelty(
        self,
        window_segments: List[Dict[str, Any]],
        previous_tokens: List[set],
    ) -> float:
        if not window_segments:
            return 0.0
        window_tokens = set()
        for seg in window_segments:
            text = seg.get("text", "")
            window_tokens.update(self._tokenize(text))
        if not window_tokens:
            return 0.0
        prev_union = set().union(*previous_tokens) if previous_tokens else set()
        novel_tokens = window_tokens - prev_union
        return float(len(novel_tokens) / max(len(window_tokens), 1))

    def _calculate_pause_seconds(
        self, pause_events: List[Event], window_start: float, window_end: float
    ) -> float:
        total = 0.0
        for event in pause_events:
            overlap_start = max(window_start, event.time_start)
            overlap_end = min(window_end, event.time_end)
            if overlap_end > overlap_start:
                total += overlap_end - overlap_start
        return total

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        pauses_data: Optional[Dict[str, Any]] = None,
        echoes_data: Optional[Dict[str, Any]] = None,
        loops_data: Optional[Dict[str, Any]] = None,
        similarity_data: Optional[Dict[str, Any]] = None,
        sentiment_data: Optional[Dict[str, Any]] = None,
        transcript_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not segments:
            return {"events": [], "stats": {}, "timeseries": [], "zones": []}

        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )

        transcript_hash = transcript_hash or compute_transcript_identity_hash(segments)

        window_length = float(getattr(self.config, "window_length_seconds", 60.0))
        window_step = float(getattr(self.config, "window_step_seconds", 30.0))
        stall_percentile = float(
            getattr(self.config, "stall_threshold_percentile", 0.15)
        )
        min_stall_duration = float(
            getattr(self.config, "min_stall_duration_seconds", 30.0)
        )
        cliff_threshold = float(getattr(self.config, "momentum_cliff_threshold", -0.2))
        novelty_lookback = int(getattr(self.config, "novelty_lookback_windows", 3))
        weights = getattr(self.config, "weights", {}) or {}

        # Inputs
        pause_events = [
            e for e in (pauses_data or {}).get("events", []) if isinstance(e, Event)
        ]
        if not pause_events and pauses_data and "events" in pauses_data:
            pause_events = [Event.from_dict(d) for d in pauses_data.get("events", [])]
        echo_events = [
            e for e in (echoes_data or {}).get("events", []) if isinstance(e, Event)
        ]
        if not echo_events and echoes_data and "events" in echoes_data:
            echo_events = [Event.from_dict(d) for d in echoes_data.get("events", [])]

        loops = []
        if loops_data:
            loops = loops_data.get("loops", []) or loops_data.get(
                "conversation_loops", []
            )

        # Sentiment map
        sentiment_map = {}
        if sentiment_data:
            sentiment_segments = sentiment_data.get("segments_with_sentiment", [])
            for seg in sentiment_segments:
                sentiment = seg.get("sentiment", {})
                if "compound" in sentiment:
                    sentiment_map[seg.get("start", 0.0)] = sentiment["compound"]

        # Time windows
        total_duration = max(seg.get("end", seg.get("start", 0.0)) for seg in segments)
        windows = []
        t = 0.0
        while t < total_duration:
            windows.append((t, min(t + window_length, total_duration)))
            t += window_step

        timeseries = []
        novelty_history: List[set] = []
        scores = []

        for window_start, window_end in windows:
            window_segments = self._window_segments(segments, window_start, window_end)
            pause_seconds = self._calculate_pause_seconds(
                pause_events, window_start, window_end
            )
            pause_rate = pause_seconds / max(window_end - window_start, 1e-6)

            echo_rate = sum(
                1
                for e in echo_events
                if e.time_start >= window_start and e.time_start < window_end
            ) / max((window_end - window_start) / 60.0, 1e-6)

            loop_rate = 0.0
            if loops:
                loop_rate = sum(
                    1
                    for loop in loops
                    if getattr(loop, "turn_1_timestamp", 0.0) >= window_start
                    and getattr(loop, "turn_1_timestamp", 0.0) < window_end
                ) / max((window_end - window_start) / 60.0, 1e-6)

            repetition_rate = 0.0
            if similarity_data:
                repetition_events = similarity_data.get("repetition_events", [])
                if repetition_events:
                    repetition_rate = sum(
                        1
                        for e in repetition_events
                        if e.get("start", 0.0) >= window_start
                        and e.get("start", 0.0) < window_end
                    ) / max((window_end - window_start) / 60.0, 1e-6)

            turn_energy = self._calculate_turn_energy(window_segments)

            # Novelty
            novelty = self._calculate_novelty(
                window_segments, novelty_history[-novelty_lookback:]
            )
            window_tokens = set()
            for seg in window_segments:
                window_tokens.update(self._tokenize(seg.get("text", "")))
            novelty_history.append(window_tokens)

            sentiment_volatility = 0.0
            if sentiment_map:
                window_sentiments = [
                    sentiment_map.get(seg.get("start", 0.0))
                    for seg in window_segments
                    if seg.get("start", 0.0) in sentiment_map
                ]
                if window_sentiments:
                    sentiment_volatility = float(np.std(window_sentiments))

            metrics = {
                "pause_rate": float(min(1.0, pause_rate)),
                "echo_rate": float(echo_rate),
                "loop_rate": float(loop_rate),
                "repetition_rate": float(repetition_rate),
                "turn_energy": float(turn_energy),
                "novelty": float(novelty),
                "sentiment_volatility": float(sentiment_volatility),
            }

            score = (
                weights.get("pause_rate", -0.3) * metrics["pause_rate"]
                + weights.get("repetition_rate", -0.3)
                * min(1.0, metrics["repetition_rate"])
                + weights.get("loop_rate", -0.2) * min(1.0, metrics["loop_rate"])
                + weights.get("novelty", 0.4) * metrics["novelty"]
                + weights.get("turn_energy", 0.3) * metrics["turn_energy"]
            )
            metrics["momentum_score"] = float(score)

            timeseries.append(
                {
                    "window_start": window_start,
                    "window_end": window_end,
                    "metrics": metrics,
                }
            )
            scores.append(score)

        # Detect stall zones
        stall_threshold = (
            float(np.percentile(scores, stall_percentile * 100)) if scores else 0.0
        )
        zones = []
        current_zone = None
        for window in timeseries:
            score = window["metrics"]["momentum_score"]
            if score <= stall_threshold:
                if current_zone is None:
                    current_zone = {
                        "start": window["window_start"],
                        "end": window["window_end"],
                        "scores": [score],
                    }
                else:
                    current_zone["end"] = window["window_end"]
                    current_zone["scores"].append(score)
            else:
                if current_zone:
                    zones.append(current_zone)
                current_zone = None
        if current_zone:
            zones.append(current_zone)

        # Filter by min duration
        zones = [z for z in zones if (z["end"] - z["start"]) >= min_stall_duration]

        # Detect cliffs
        cliffs = []
        for prev, curr in zip(timeseries, timeseries[1:], strict=False):
            delta = (
                curr["metrics"]["momentum_score"] - prev["metrics"]["momentum_score"]
            )
            if delta <= cliff_threshold:
                cliffs.append(
                    {
                        "time_start": curr["window_start"],
                        "time_end": curr["window_end"],
                        "delta": float(delta),
                    }
                )

        # Events
        events: List[Event] = []
        for zone in zones:
            events.append(
                Event(
                    event_id=generate_event_id(
                        transcript_hash,
                        "stall_zone",
                        None,
                        None,
                        zone["start"],
                        zone["end"],
                    ),
                    kind="stall_zone",
                    time_start=zone["start"],
                    time_end=zone["end"],
                    speaker=None,
                    segment_start_idx=None,
                    segment_end_idx=None,
                    severity=min(1.0, 1 - float(np.mean(zone["scores"]))),
                    score=float(np.mean(zone["scores"])),
                    evidence=[
                        {
                            "source": "momentum",
                            "feature": "stall_threshold",
                            "value": stall_threshold,
                        }
                    ],
                    links=[],
                )
            )

        for cliff in cliffs:
            events.append(
                Event(
                    event_id=generate_event_id(
                        transcript_hash,
                        "momentum_cliff",
                        None,
                        None,
                        cliff["time_start"],
                        cliff["time_end"],
                    ),
                    kind="momentum_cliff",
                    time_start=cliff["time_start"],
                    time_end=cliff["time_end"],
                    speaker=None,
                    segment_start_idx=None,
                    segment_end_idx=None,
                    severity=min(1.0, abs(cliff["delta"])),
                    score=cliff["delta"],
                    evidence=[
                        {
                            "source": "momentum",
                            "feature": "delta",
                            "value": cliff["delta"],
                        }
                    ],
                    links=[],
                )
            )

        stats = {
            "window_length_seconds": window_length,
            "window_step_seconds": window_step,
            "stall_threshold": stall_threshold,
            "stall_zone_count": len(zones),
            "momentum_cliff_count": len(cliffs),
        }

        return {
            "events": events,
            "stats": stats,
            "timeseries": timeseries,
            "zones": zones,
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

            pauses_result = context.get_analysis_result("pauses")
            echoes_result = context.get_analysis_result("echoes")
            loops_result = context.get_analysis_result("conversation_loops")
            similarity_result = context.get_analysis_result(
                "semantic_similarity_advanced"
            ) or context.get_analysis_result("semantic_similarity")
            sentiment_result = context.get_analysis_result("sentiment")

            results = self.analyze(
                context.get_segments(),
                context.get_speaker_map(),
                pauses_data=pauses_result,
                echoes_data=echoes_result,
                loops_data=loops_result,
                similarity_data=similarity_result,
                sentiment_data=sentiment_result,
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
        os.makedirs(output_structure.global_data_dir, exist_ok=True)
        os.makedirs(output_structure.global_charts_dir, exist_ok=True)

        events: List[Event] = results.get("events", [])
        stats: Dict[str, Any] = results.get("stats", {})
        timeseries: List[Dict[str, Any]] = results.get("timeseries", [])
        zones: List[Dict[str, Any]] = results.get("zones", [])

        save_events_json(events, output_structure, "momentum.events.json")
        save_json(stats, str(output_structure.global_data_dir / "momentum.stats.json"))
        save_json(
            timeseries,
            str(output_structure.global_data_dir / "momentum.timeseries.json"),
        )

        if zones:
            save_csv(
                [[z["start"], z["end"], float(np.mean(z["scores"]))] for z in zones],
                str(output_structure.global_data_dir / "stall_zones.csv"),
                header=["start", "end", "avg_score"],
            )

        # Chart
        if timeseries:
            xs = [w["window_start"] for w in timeseries]
            x_display, x_label = time_axis_display(xs)
            ys = [w["metrics"]["momentum_score"] for w in timeseries]
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_MOMENTUM_TIMESERIES,
                module=self.module_name,
                name="momentum",
                scope="global",
                chart_intent="line_timeseries",
                title="Momentum Over Time",
                x_label=x_label,
                y_label="Momentum Score",
                markers=False,
                series=[{"name": "Momentum", "x": x_display, "y": ys}],
            )
            output_service.save_chart(spec, chart_type="timeseries")

        output_service.save_summary(stats, {}, analysis_metadata={})
