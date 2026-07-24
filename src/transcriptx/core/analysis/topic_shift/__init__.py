"""Topic-shift / chapter segmentation analysis module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.topic_shift.analyze import run_topic_shift_analysis
from transcriptx.core.analysis.topic_shift.enrichment import (
    maybe_run_topic_shift_enrichment,
)
from transcriptx.core.analysis.topic_shift.schemas import (
    EventsEnvelopeModel,
    SpansEnvelopeModel,
    StatsEnvelopeModel,
)
from transcriptx.core.analysis.topic_shift.store import (
    begin_attempt,
    commit_and_activate,
    record_failed_attempt,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.viz_ids import VIZ_TOPIC_SHIFT_TIMELINE
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import LineTimeSeriesSpec
from transcriptx.io import save_json

logger = get_logger()


class TopicShiftAnalysis(AnalysisModule):
    """Embedding change-point chapter spans (deterministic; optional LLM sidecar later)."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "topic_shift"
        self._settings = get_config().analysis.topic_shift
        self._metadata: Dict[str, Any] | None = None

    def _settings_mapping(self) -> dict[str, Any]:
        s = self._settings
        return {
            "window_size": int(s.window_size),
            "stride": int(s.stride),
            "smooth_width": int(s.smooth_width),
            "edge_exclude": int(s.edge_exclude),
            "min_windows_for_detection": int(s.min_windows_for_detection),
            "min_gap_windows": int(s.min_gap_windows),
            "min_gap_seconds": float(s.min_gap_seconds),
            "max_shifts": int(s.max_shifts),
            "centroid_radius": int(s.centroid_radius),
            "centroid_threshold": float(s.centroid_threshold),
            "min_text_chars": int(s.min_text_chars),
            "max_windows_per_chunk": int(s.max_windows_per_chunk),
            "chunk_overlap_windows": int(s.chunk_overlap_windows),
            "min_duration_for_rate_seconds": float(s.min_duration_for_rate_seconds),
            "en_model": str(s.en_model),
            "multi_model": str(s.multi_model),
            "batch_size": int(s.batch_size),
            "lru_size": int(s.lru_size),
            "timeout_seconds": float(s.timeout_seconds),
            "thresholds": {
                "k_mad": float(s.k_mad),
                "absolute_floor": float(s.absolute_floor),
                "min_prominence": float(s.min_prominence),
            },
        }

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        allow_downloads = not bool(
            os.environ.get("TRANSCRIPTX_DISABLE_DOWNLOADS", "").strip()
            in {"1", "true", "TRUE", "yes", "YES"}
        )
        return run_topic_shift_analysis(
            segments,
            metadata=self._metadata,
            settings=self._settings_mapping(),
            generation_id="pending",
            allow_downloads=allow_downloads,
        )

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        meta = getattr(context, "transcript_metadata", None)
        if isinstance(meta, dict):
            self._metadata = meta
        else:
            self._metadata = None
        try:
            return super().run_from_context(context)
        finally:
            self._metadata = None

    def _save_results(
        self,
        results: Dict[str, Any],
        output_service: "OutputService",
    ) -> None:
        module_dir = Path(output_service.output_structure.module_dir)
        staged = begin_attempt(module_dir)
        try:
            # Stamp generation id into envelopes
            gid = staged.generation_id
            for key in ("spans_envelope", "events_envelope", "stats_envelope"):
                env = results.get(key)
                if isinstance(env, dict):
                    env["deterministic_generation_id"] = gid

            spans_env = SpansEnvelopeModel.model_validate(results["spans_envelope"])
            events_env = EventsEnvelopeModel.model_validate(results["events_envelope"])
            stats_env = StatsEnvelopeModel.model_validate(results["stats_envelope"])

            staged.write_json(
                "topic_shift.spans.json", spans_env.model_dump(mode="json")
            )
            staged.write_json(
                "topic_shift.events.json", events_env.model_dump(mode="json")
            )
            staged.write_json(
                "topic_shift.stats.json", stats_env.model_dump(mode="json")
            )
            commit_and_activate(staged)

            # Mirror active files into standard data/global for discovery
            data_dir = Path(output_service.output_structure.global_data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "topic_shift.spans.json",
                "topic_shift.events.json",
                "topic_shift.stats.json",
            ):
                src = staged.directory / name
                dest = data_dir / name
                save_json(
                    __import__("json").loads(src.read_text(encoding="utf-8")),
                    str(dest),
                )
                output_service.record_file(dest)

            # In-memory payload for PipelineContext
            results["deterministic_generation_id"] = gid
            results["schema_version"] = spans_env.schema_version
            results["coverage_spans"] = spans_env.coverage_spans
            results["stats"] = stats_env.model_dump(mode="json")

            self._save_charts(results, output_service)
            # Enrichment is a separate transaction; never fail deterministic ACTIVE.
            try:
                enrichment = maybe_run_topic_shift_enrichment(
                    module_output_dir=module_dir,
                    spans_envelope=spans_env.model_dump(mode="json"),
                )
                results["enrichment"] = enrichment
                enrich_path = (
                    Path(output_service.output_structure.global_data_dir)
                    / "topic_shift.enrichment.json"
                )
                if enrich_path.is_file():
                    output_service.record_file(enrich_path)
            except Exception:
                logger.warning(
                    "topic_shift enrichment soft-failed; deterministic ACTIVE kept",
                    exc_info=True,
                )
        except Exception:
            record_failed_attempt(module_dir, staged.generation_id)
            raise

    def _save_charts(
        self,
        results: Dict[str, Any],
        output_service: "OutputService",
    ) -> None:
        spans = results.get("spans_envelope", {}).get("coverage_spans") or []
        events = results.get("events_envelope", {}).get("events") or []
        if not spans and not events:
            return
        starts = [float(s.get("time_start") or 0.0) for s in spans]
        durations = [
            max(
                0.0, float(s.get("time_end") or 0.0) - float(s.get("time_start") or 0.0)
            )
            for s in spans
        ]
        if not starts:
            return
        x_values, x_label = time_axis_display(starts)
        # Marker series for boundaries
        bx = [float(e.get("time_start") or 0.0) for e in events]
        by = [float(e.get("severity") or 0.0) for e in events]
        series = [
            {
                "name": "chapter spans",
                "x": list(x_values) if x_values else [t / 60.0 for t in starts],
                "y": durations,
            }
        ]
        if bx:
            bx_disp, _ = time_axis_display(bx)
            series.append(
                {
                    "name": "topic shifts",
                    "x": list(bx_disp) if bx_disp else [t / 60.0 for t in bx],
                    "y": by,
                }
            )
        try:
            output_service.save_chart(
                LineTimeSeriesSpec(
                    viz_id=VIZ_TOPIC_SHIFT_TIMELINE,
                    module=self.module_name,
                    name="topic_shift_timeline",
                    scope="global",
                    chart_intent="line_timeseries",
                    title="Topic-shift chapters (span duration) and boundaries",
                    x_label=x_label or "Time",
                    y_label="Duration / shift strength",
                    markers=True,
                    series=series,
                ),
                chart_type="timeline",
            )
        except Exception:
            # Charts optional — do not fail deterministic commit
            pass
