"""
Temporal Dynamics Analysis Module for TranscriptX.

This module analyzes how conversation metrics evolve over time, including:
- Sentiment trends
- Emotion distribution changes
- Topic shifts
- Speaking rate variations
- Engagement patterns
- Phase detection (opening, main discussion, closing)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional
import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.viz_ids import (
    VIZ_TEMPORAL_ENGAGEMENT_TIMESERIES,
    VIZ_TEMPORAL_SPEAKING_RATE_TIMESERIES,
    VIZ_TEMPORAL_SENTIMENT_TIMESERIES,
    VIZ_TEMPORAL_PHASE_DETECTION,
    VIZ_TEMPORAL_DASHBOARD,
    VIZ_TEMPORAL_DASHBOARD_SPEAKING_RATE,
)
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec

logger = get_logger()


class TemporalDynamicsAnalysis(AnalysisModule):
    """
    Temporal dynamics analysis module.

    This module analyzes how conversation metrics evolve over time,
    providing insights into conversation flow, engagement patterns,
    and phase transitions.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the temporal dynamics analysis module."""
        super().__init__(config)
        self.module_name = "temporal_dynamics"

        # Get config from profile
        from transcriptx.core.utils.config import get_config

        profile_config = get_config().analysis.temporal_dynamics

        # Use config values, with fallback to provided config or defaults
        self.window_size = self.config.get("window_size", profile_config.window_size)
        self.metrics_to_track = self.config.get(
            "metrics_to_track",
            ["sentiment", "emotion", "speaking_rate", "turn_frequency", "engagement"],
        )

        # Store config values
        self.weight_segment_factor = profile_config.weight_segment_factor
        self.weight_length_factor = profile_config.weight_length_factor
        self.weight_question_factor = profile_config.weight_question_factor
        self.max_segments_normalization = profile_config.max_segments_normalization
        self.max_questions_normalization = profile_config.max_questions_normalization
        self.opening_phase_percentage = profile_config.opening_phase_percentage
        self.opening_phase_max_seconds = profile_config.opening_phase_max_seconds
        self.closing_phase_percentage = profile_config.closing_phase_percentage
        self.closing_phase_max_seconds = profile_config.closing_phase_max_seconds
        self.sentiment_change_threshold = profile_config.sentiment_change_threshold
        self.engagement_change_threshold = profile_config.engagement_change_threshold
        self.speaking_rate_change_threshold = (
            profile_config.speaking_rate_change_threshold
        )

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        sentiment_data: Optional[Dict[str, Any]] = None,
        emotion_data: Optional[Dict[str, Any]] = None,
        topic_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform temporal dynamics analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping
            sentiment_data: Optional sentiment analysis results
            emotion_data: Optional emotion analysis results
            topic_data: Optional topic modeling results

        Returns:
            Dictionary containing temporal dynamics analysis results
        """
        if not segments:
            return {
                "time_windows": [],
                "trends": {},
                "phase_detection": {},
                "peak_periods": [],
                "error": "No segments provided",
            }

        # Get conversation duration
        total_duration = max(seg.get("end", seg.get("start", 0)) for seg in segments)

        # Create time windows
        time_windows = self._create_time_windows(total_duration)

        # Calculate metrics for each window
        window_metrics = []
        for window in time_windows:
            window_segments = self._get_segments_in_window(
                segments, window["window_start"], window["window_end"]
            )
            metrics = self._calculate_window_metrics(
                window_segments, speaker_map, sentiment_data, emotion_data, topic_data
            )
            window["metrics"] = metrics["global"]
            window["speaker_metrics"] = metrics["speakers"]
            window_metrics.append(window)

        # Detect trends
        trends = self._detect_trends(window_metrics)

        # Detect phases
        phase_detection = self._detect_phases(window_metrics, total_duration)

        # Identify peak periods
        peak_periods = self._identify_peak_periods(window_metrics)

        return {
            "time_windows": window_metrics,
            "trends": trends,
            "phase_detection": phase_detection,
            "peak_periods": peak_periods,
            "total_duration": total_duration,
            "window_size": self.window_size,
            "num_windows": len(window_metrics),
        }

    def _create_time_windows(self, total_duration: float) -> List[Dict[str, float]]:
        """Create non-overlapping time windows."""
        windows = []
        current_start = 0.0

        while current_start < total_duration:
            window_end = min(current_start + self.window_size, total_duration)
            windows.append(
                {
                    "window_start": current_start,
                    "window_end": window_end,
                    "duration": window_end - current_start,
                }
            )
            current_start = window_end

        return windows

    def _get_segments_in_window(
        self, segments: List[Dict[str, Any]], window_start: float, window_end: float
    ) -> List[Dict[str, Any]]:
        """Get segments that overlap with the time window."""
        window_segments = []
        for seg in segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", seg.get("start", 0))

            # Check if segment overlaps with window
            if seg_start < window_end and seg_end > window_start:
                window_segments.append(seg)

        return window_segments

    def _calculate_window_metrics(
        self,
        window_segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str],
        sentiment_data: Optional[Dict[str, Any]] = None,
        emotion_data: Optional[Dict[str, Any]] = None,
        topic_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculate metrics for a time window."""
        if not window_segments:
            return {
                "global": {
                    "speaking_rate": 0.0,
                    "turn_frequency": 0.0,
                    "engagement_score": 0.0,
                    "avg_sentiment": None,
                    "dominant_emotion": None,
                    "num_segments": 0,
                    "num_speakers": 0,
                },
                "speakers": {},
            }

        # Basic metrics
        num_segments = len(window_segments)
        window_duration = self.window_size
        total_words = sum(len(seg.get("text", "").split()) for seg in window_segments)
        speaking_rate = (
            (total_words / window_duration) * 60.0 if window_duration > 0 else 0.0
        )

        # Turn frequency (speaker changes per minute)
        speaker_changes = sum(
            1
            for i in range(1, len(window_segments))
            if window_segments[i].get("speaker")
            != window_segments[i - 1].get("speaker")
        )
        turn_frequency = (
            (speaker_changes / window_duration) * 60.0 if window_duration > 0 else 0.0
        )

        # Engagement score (combination of factors)
        avg_segment_length = (
            np.mean([len(seg.get("text", "").split()) for seg in window_segments])
            if window_segments
            else 0
        )
        question_count = sum(1 for seg in window_segments if "?" in seg.get("text", ""))
        engagement_score = self._calculate_engagement_score(
            num_segments, avg_segment_length, question_count, window_duration
        )

        # Sentiment metrics (if available)
        avg_sentiment = None
        if sentiment_data or any("sentiment" in seg for seg in window_segments):
            sentiment_scores = []
            for seg in window_segments:
                if "sentiment" in seg:
                    compound = seg["sentiment"].get("compound", 0)
                    sentiment_scores.append(compound)
            if sentiment_scores:
                avg_sentiment = np.mean(sentiment_scores)

        # Emotion metrics (if available)
        dominant_emotion = None
        if emotion_data or any(
            "context_emotion" in seg or "nrc_emotion" in seg for seg in window_segments
        ):
            emotion_counts = defaultdict(int)
            for seg in window_segments:
                if "context_emotion" in seg:
                    emotion_counts[seg["context_emotion"]] += 1
                elif "nrc_emotion" in seg:
                    nrc_data = seg.get("nrc_emotion", {})
                    if nrc_data:
                        dominant = max(nrc_data.items(), key=lambda x: x[1])[0]
                        emotion_counts[dominant] += 1
            if emotion_counts:
                dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0]

        # Speaker-specific metrics
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        speaker_metrics = {}
        speaker_segments_map = defaultdict(list)
        for seg in window_segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], window_segments
            )
            if speaker and is_named_speaker(speaker):
                speaker_segments_map[speaker].append(seg)

        for speaker, segs in speaker_segments_map.items():
            speaker_words = sum(len(seg.get("text", "").split()) for seg in segs)
            speaker_rate = (
                (speaker_words / window_duration) * 60.0 if window_duration > 0 else 0.0
            )

            speaker_sentiment = None
            if any("sentiment" in seg for seg in segs):
                sentiment_scores = [
                    seg["sentiment"].get("compound", 0)
                    for seg in segs
                    if "sentiment" in seg
                ]
                if sentiment_scores:
                    speaker_sentiment = np.mean(sentiment_scores)

            speaker_metrics[speaker] = {
                "speaking_rate": speaker_rate,
                "num_segments": len(segs),
                "avg_sentiment": speaker_sentiment,
            }

        # Count unique speakers
        unique_speakers = len(speaker_segments_map)

        return {
            "global": {
                "speaking_rate": round(speaking_rate, 2),
                "turn_frequency": round(turn_frequency, 2),
                "engagement_score": round(engagement_score, 3),
                "avg_sentiment": (
                    round(avg_sentiment, 3) if avg_sentiment is not None else None
                ),
                "dominant_emotion": dominant_emotion,
                "num_segments": num_segments,
                "num_speakers": unique_speakers,
            },
            "speakers": speaker_metrics,
        }

    def _calculate_engagement_score(
        self,
        num_segments: int,
        avg_segment_length: float,
        question_count: int,
        window_duration: float,
    ) -> float:
        """Calculate engagement score (0-1) based on multiple factors."""
        # Normalize factors using config values
        segment_factor = min(num_segments / self.max_segments_normalization, 1.0)
        length_factor = min(
            avg_segment_length / 20.0, 1.0
        )  # Normalize to max 20 words (could be configurable)
        question_factor = min(question_count / self.max_questions_normalization, 1.0)

        # Weighted combination using config weights
        engagement = (
            self.weight_segment_factor * segment_factor
            + self.weight_length_factor * length_factor
            + self.weight_question_factor * question_factor
        )

        return min(max(engagement, 0.0), 1.0)

    def _detect_trends(self, window_metrics: List[Dict[str, Any]]) -> Dict[str, str]:
        """Detect trends in metrics across windows."""
        if len(window_metrics) < 2:
            return {}

        trends = {}

        # Sentiment trend
        sentiment_values = [
            w["metrics"].get("avg_sentiment")
            for w in window_metrics
            if w["metrics"].get("avg_sentiment") is not None
        ]
        if len(sentiment_values) >= 2:
            trend = (
                "increasing"
                if sentiment_values[-1] > sentiment_values[0]
                else "decreasing"
            )
            if (
                abs(sentiment_values[-1] - sentiment_values[0])
                < self.sentiment_change_threshold
            ):
                trend = "stable"
            trends["sentiment_trend"] = trend

        # Engagement trend
        engagement_values = [
            w["metrics"].get("engagement_score", 0) for w in window_metrics
        ]
        if len(engagement_values) >= 2:
            trend = (
                "increasing"
                if engagement_values[-1] > engagement_values[0]
                else "decreasing"
            )
            if (
                abs(engagement_values[-1] - engagement_values[0])
                < self.engagement_change_threshold
            ):
                trend = "stable"
            trends["engagement_trend"] = trend

        # Speaking rate trend
        speaking_rate_values = [
            w["metrics"].get("speaking_rate", 0) for w in window_metrics
        ]
        if len(speaking_rate_values) >= 2:
            trend = (
                "increasing"
                if speaking_rate_values[-1] > speaking_rate_values[0]
                else "decreasing"
            )
            if (
                abs(speaking_rate_values[-1] - speaking_rate_values[0])
                < self.speaking_rate_change_threshold
            ):
                trend = "stable"
            trends["speaking_rate_trend"] = trend

        return trends

    def _detect_phases(
        self, window_metrics: List[Dict[str, Any]], total_duration: float
    ) -> Dict[str, Dict[str, float]]:
        """Detect conversation phases (opening, main, closing)."""
        if len(window_metrics) < 3:
            return {}

        # Opening phase: first X% or first Y seconds, whichever is smaller
        opening_duration = min(
            total_duration * self.opening_phase_percentage,
            self.opening_phase_max_seconds,
        )

        # Closing phase: last X% or last Y seconds, whichever is smaller
        closing_start = max(
            0,
            total_duration
            - min(
                total_duration * self.closing_phase_percentage,
                self.closing_phase_max_seconds,
            ),
        )

        # Main phase: everything in between
        main_start = opening_duration
        main_end = closing_start

        return {
            "opening": {
                "start": 0.0,
                "end": opening_duration,
                "duration": opening_duration,
            },
            "main": {
                "start": main_start,
                "end": main_end,
                "duration": main_end - main_start,
            },
            "closing": {
                "start": closing_start,
                "end": total_duration,
                "duration": total_duration - closing_start,
            },
        }

    def _identify_peak_periods(
        self, window_metrics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify periods of peak engagement."""
        if not window_metrics:
            return []

        # Calculate engagement scores
        engagement_scores = [
            w["metrics"].get("engagement_score", 0) for w in window_metrics
        ]

        if not engagement_scores:
            return []

        # Find windows above 75th percentile
        threshold = np.percentile(engagement_scores, 75)

        peak_periods = []
        for window in window_metrics:
            if window["metrics"].get("engagement_score", 0) >= threshold:
                peak_periods.append(
                    {
                        "start": window["window_start"],
                        "end": window["window_end"],
                        "engagement_score": window["metrics"].get(
                            "engagement_score", 0
                        ),
                        "metrics": window["metrics"],
                    }
                )

        return peak_periods

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """
        Run temporal dynamics analysis using PipelineContext (can access cached results).

        Args:
            context: PipelineContext containing transcript data and cached results

        Returns:
            Dictionary containing analysis results and metadata
        """
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_start,
                log_analysis_complete,
                log_analysis_error,
            )

            log_analysis_start(self.module_name, context.transcript_path)

            # Extract data from context
            segments = context.get_segments()
            speaker_map = context.get_speaker_map()

            # Try to get cached results from dependencies
            sentiment_result = context.get_analysis_result("sentiment")
            emotion_result = context.get_analysis_result("emotion")
            topic_result = context.get_analysis_result("topic_modeling")

            # Enrich segments with dependency data if available
            if sentiment_result:
                segments_with_sentiment = sentiment_result.get(
                    "segments_with_sentiment", []
                )
                if segments_with_sentiment:
                    # Merge sentiment data into segments by matching timestamps
                    sentiment_map = {
                        seg.get("start", 0): seg for seg in segments_with_sentiment
                    }
                    for seg in segments:
                        seg_start = seg.get("start", 0)
                        if seg_start in sentiment_map:
                            seg["sentiment"] = sentiment_map[seg_start].get(
                                "sentiment", {}
                            )

            if emotion_result:
                segments_with_emotion = emotion_result.get("segments_with_emotion", [])
                if segments_with_emotion:
                    emotion_map = {
                        seg.get("start", 0): seg for seg in segments_with_emotion
                    }
                    for seg in segments:
                        seg_start = seg.get("start", 0)
                        if seg_start in emotion_map:
                            emotion_seg = emotion_map[seg_start]
                            if "context_emotion" in emotion_seg:
                                seg["context_emotion"] = emotion_seg["context_emotion"]
                            if "nrc_emotion" in emotion_seg:
                                seg["nrc_emotion"] = emotion_seg["nrc_emotion"]

            # Perform analysis
            results = self.analyze(
                segments,
                speaker_map,
                sentiment_data=sentiment_result,
                emotion_data=emotion_result,
                topic_data=topic_result,
            )

            # Create output service and save results
            from transcriptx.core.output.output_service import create_output_service

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)

            # Store result in context for reuse by other modules
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

        except Exception as e:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(e))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(e),
                "results": {},
            }

    def save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """Save temporal dynamics analysis results."""
        self._save_results(results, output_service)

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """Save results using OutputService (new interface)."""
        # Save main results as JSON
        output_service.save_data(results, "temporal_dynamics", format_type="json")

        # Save time window metrics as CSV
        if results.get("time_windows"):
            csv_rows = []
            for window in results["time_windows"]:
                row = {
                    "window_start": window["window_start"],
                    "window_end": window["window_end"],
                    "duration": window["duration"],
                    **window["metrics"],
                }
                csv_rows.append(row)
            output_service.save_data(csv_rows, "temporal_dynamics", format_type="csv")

        # Generate visualizations
        self._generate_visualizations(results, output_service)

        # Save summary
        global_stats = {
            "total_duration": results.get("total_duration", 0),
            "num_windows": results.get("num_windows", 0),
            "window_size": results.get("window_size", 30.0),
            "trends": results.get("trends", {}),
            "phases": results.get("phase_detection", {}),
        }
        output_service.save_summary(global_stats, {}, analysis_metadata={})

    def _generate_visualizations(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """Generate temporal dynamics visualizations."""
        try:
            time_windows = results.get("time_windows", [])
            if not time_windows:
                return

            # Create time series plots
            self._create_time_series_plots(time_windows, output_service)

            # Create phase detection timeline
            self._create_phase_timeline(
                results.get("phase_detection", {}), output_service
            )

            # Create multi-metric dashboard
            self._create_dashboard(time_windows, output_service)

        except Exception as e:
            logger.warning(f"Failed to generate visualizations: {e}")

    def _create_time_series_plots(
        self, time_windows: List[Dict[str, Any]], output_service: "OutputService"
    ) -> None:
        """Create time series plots for key metrics."""
        if not time_windows:
            return

        # Extract time points and metrics
        window_centers = [
            (w["window_start"] + w["window_end"]) / 2 for w in time_windows
        ]

        # Engagement score plot
        engagement_scores = [
            w["metrics"].get("engagement_score", 0) for w in time_windows
        ]
        if any(engagement_scores):
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_TEMPORAL_ENGAGEMENT_TIMESERIES,
                module=self.module_name,
                name="engagement_timeseries",
                scope="global",
                chart_intent="line_timeseries",
                title="Engagement Over Time",
                x_label="Time (seconds)",
                y_label="Engagement Score",
                markers=True,
                series=[
                    {"name": "Engagement", "x": window_centers, "y": engagement_scores}
                ],
            )
            output_service.save_chart(spec)

        # Speaking rate plot
        speaking_rates = [w["metrics"].get("speaking_rate", 0) for w in time_windows]
        if any(speaking_rates):
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_TEMPORAL_SPEAKING_RATE_TIMESERIES,
                module=self.module_name,
                name="speaking_rate_timeseries",
                scope="global",
                chart_intent="line_timeseries",
                title="Speaking Rate Over Time",
                x_label="Time (seconds)",
                y_label="Speaking Rate (words/min)",
                markers=True,
                series=[
                    {
                        "name": "Speaking Rate",
                        "x": window_centers,
                        "y": speaking_rates,
                    }
                ],
            )
            output_service.save_chart(spec)

        # Sentiment plot (if available)
        sentiment_values = [
            w["metrics"].get("avg_sentiment")
            for w in time_windows
            if w["metrics"].get("avg_sentiment") is not None
        ]
        if sentiment_values:
            sentiment_times = [
                (w["window_start"] + w["window_end"]) / 2
                for w in time_windows
                if w["metrics"].get("avg_sentiment") is not None
            ]
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_TEMPORAL_SENTIMENT_TIMESERIES,
                module=self.module_name,
                name="sentiment_timeseries",
                scope="global",
                chart_intent="line_timeseries",
                title="Sentiment Over Time",
                x_label="Time (seconds)",
                y_label="Average Sentiment",
                markers=True,
                series=[
                    {"name": "Sentiment", "x": sentiment_times, "y": sentiment_values}
                ],
            )
            output_service.save_chart(spec)

    def _create_phase_timeline(
        self,
        phase_detection: Dict[str, Dict[str, float]],
        output_service: "OutputService",
    ) -> None:
        """Create phase detection timeline visualization."""
        if not phase_detection:
            return

        phases = ["opening", "main", "closing"]
        durations = []
        labels = []
        for i, phase_name in enumerate(phases):
            if phase_name in phase_detection:
                phase = phase_detection[phase_name]
                start = phase.get("start", 0)
                end = phase.get("end", 0)
                duration = end - start
                labels.append(phase_name.capitalize())
                durations.append(duration)

        if labels:
            spec = BarCategoricalSpec(
                viz_id=VIZ_TEMPORAL_PHASE_DETECTION,
                module=self.module_name,
                name="phase_detection",
                scope="global",
                chart_intent="bar_categorical",
                title="Conversation Phase Durations",
                x_label="Phase",
                y_label="Duration (seconds)",
                categories=labels,
                values=durations,
            )
            output_service.save_chart(spec)

    def _create_dashboard(
        self, time_windows: List[Dict[str, Any]], output_service: "OutputService"
    ) -> None:
        """Create multi-metric dashboards (engagement/turn/segments in one chart;
        speaking rate in a separate chart so scale is readable)."""
        if not time_windows:
            return

        window_centers = [
            (w["window_start"] + w["window_end"]) / 2 for w in time_windows
        ]
        # Engagement, turn frequency, num segments share a similar scale
        series_metrics = [
            {
                "name": "Engagement",
                "x": window_centers,
                "y": [w["metrics"].get("engagement_score", 0) for w in time_windows],
            },
            {
                "name": "Turn Frequency",
                "x": window_centers,
                "y": [w["metrics"].get("turn_frequency", 0) for w in time_windows],
            },
            {
                "name": "Num Segments",
                "x": window_centers,
                "y": [w["metrics"].get("num_segments", 0) for w in time_windows],
            },
        ]
        spec = LineTimeSeriesSpec(
            viz_id=VIZ_TEMPORAL_DASHBOARD,
            module=self.module_name,
            name="temporal_dashboard",
            scope="global",
            chart_intent="line_timeseries",
            title="Temporal Dynamics Dashboard",
            x_label="Time (seconds)",
            y_label="Value",
            markers=True,
            series=series_metrics,
        )
        output_service.save_chart(spec)

        # Speaking rate is orders of magnitude higher (wpm); separate chart
        series_speaking_rate = [
            {
                "name": "Speaking Rate",
                "x": window_centers,
                "y": [w["metrics"].get("speaking_rate", 0) for w in time_windows],
            },
        ]
        spec_sr = LineTimeSeriesSpec(
            viz_id=VIZ_TEMPORAL_DASHBOARD_SPEAKING_RATE,
            module=self.module_name,
            name="temporal_dashboard_speaking_rate",
            scope="global",
            chart_intent="line_timeseries",
            title="Temporal Dynamics – Speaking Rate",
            x_label="Time (seconds)",
            y_label="Words per minute",
            markers=True,
            series=series_speaking_rate,
        )
        output_service.save_chart(spec_sr)
