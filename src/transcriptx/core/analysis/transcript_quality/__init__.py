"""Transcript quality module — ASR confidence evidence and review."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.transcript_quality.analyze import (
    compute_asr_confidence,
    score_histogram_bins,
)
from transcriptx.core.analysis.transcript_quality.provenance import (
    resolve_provenance_from_transcript_path,
)
from transcriptx.core.analysis.transcript_quality.spans import SpanBuildConfig
from transcriptx.core.analysis.transcript_quality.words import extract_word_records
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.viz_ids import (
    VIZ_TRANSCRIPT_QUALITY_HIST,
    VIZ_TRANSCRIPT_QUALITY_TIMELINE,
)
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec


class TranscriptQualityAnalysis(AnalysisModule):
    """ASR confidence diagnostics from word-level scores when present."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "transcript_quality"
        self._settings = get_config().analysis.transcript_quality
        self._transcript_path: Optional[str] = None

    def _span_config(self) -> SpanBuildConfig:
        s = self._settings
        return SpanBuildConfig(
            low_score_threshold=float(s.low_score_threshold),
            max_gap_seconds=float(s.max_gap_seconds),
            cluster_merge_seconds=float(s.cluster_merge_seconds),
            max_spans=int(s.max_spans),
            max_clusters=int(s.max_clusters),
        )

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        provenance = resolve_provenance_from_transcript_path(self._transcript_path)
        results = compute_asr_confidence(
            segments,
            cfg=self._span_config(),
            provenance=provenance,
        )
        words, _ = extract_word_records(segments)
        results["_chart_scores"] = [
            float(w.score) for w in words if w.eligible and w.score is not None
        ]
        return results

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        self._transcript_path = getattr(context, "transcript_path", None)
        try:
            return super().run_from_context(context)
        finally:
            self._transcript_path = None

    def _save_results(
        self,
        results: Dict[str, Any],
        output_service: "OutputService",
    ) -> None:
        # Strip internal chart helper before persisting the main payload.
        persist = {k: v for k, v in results.items() if k != "_chart_scores"}
        output_service.save_data(persist, "transcript_quality", format_type="json")
        asr = persist.get("asr_confidence") or {}
        output_service.save_data(
            {
                "spans": asr.get("spans") or [],
                "clusters": asr.get("clusters") or [],
            },
            "transcript_quality_spans",
            format_type="json",
        )
        self._save_charts(results, output_service)

    def _save_charts(
        self,
        results: Dict[str, Any],
        output_service: "OutputService",
    ) -> None:
        asr = results.get("asr_confidence") or {}
        if asr.get("status") == "absent":
            return

        scores = results.get("_chart_scores")
        if isinstance(scores, list) and scores:
            hist = score_histogram_bins([float(s) for s in scores])
            if any(hist["counts"]):
                output_service.save_chart(
                    BarCategoricalSpec(
                        viz_id=VIZ_TRANSCRIPT_QUALITY_HIST,
                        module=self.module_name,
                        name="asr_score_hist",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="ASR confidence score distribution",
                        x_label="Score bin",
                        y_label="Word count",
                        categories=hist["categories"],
                        values=[float(c) for c in hist["counts"]],
                    ),
                    chart_type="distribution",
                )

        spans = asr.get("spans") or []
        if not spans:
            return
        starts = [float(s.get("start") or 0.0) for s in spans]
        means = [
            float(s["mean_score"])
            if isinstance(s.get("mean_score"), (int, float))
            else 0.0
            for s in spans
        ]
        x_values, x_label = time_axis_display(starts)
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id=VIZ_TRANSCRIPT_QUALITY_TIMELINE,
                module=self.module_name,
                name="asr_low_score_timeline",
                scope="global",
                chart_intent="line_timeseries",
                title="Low ASR confidence spans (mean score)",
                x_label=x_label or "Time",
                y_label="Mean score",
                markers=True,
                series=[
                    {
                        "name": "low-confidence spans",
                        "x": list(x_values) if x_values else [t / 60.0 for t in starts],
                        "y": means,
                    }
                ],
            ),
            chart_type="timeline",
        )
