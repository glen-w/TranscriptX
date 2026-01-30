"""
Moments analysis module for TranscriptX.

Aggregates events from multiple modules into ranked "Moments Worth Revisiting".
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.models.events import Event, generate_event_id
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.io import save_csv, save_json
from transcriptx.core.utils.viz_ids import VIZ_MOMENTS_TIMELINE
from transcriptx.core.viz.specs import LineTimeSeriesSpec

plt = lazy_pyplot()


class MomentsAnalysis(AnalysisModule):
    """Aggregate events into ranked moments."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "moments"
        self.config = get_config().analysis.moments

    def _normalize_events(self, events: List[Any]) -> List[Event]:
        normalized = []
        for event in events:
            if isinstance(event, Event):
                normalized.append(event)
            elif isinstance(event, dict):
                normalized.append(Event.from_dict(event))
        return normalized

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        pauses_data: Optional[Dict[str, Any]] = None,
        echoes_data: Optional[Dict[str, Any]] = None,
        momentum_data: Optional[Dict[str, Any]] = None,
        qa_data: Optional[Dict[str, Any]] = None,
        transcript_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )

        transcript_hash = transcript_hash or compute_transcript_identity_hash(segments)

        merge_seconds = float(getattr(self.config, "merge_seconds", 20.0))
        top_n = int(getattr(self.config, "top_n", 20))
        weight_map = getattr(self.config, "weight_map", {}) or {}
        diversity_bonus = float(getattr(self.config, "diversity_bonus", 0.2))
        multi_speaker_bonus = float(getattr(self.config, "multi_speaker_bonus", 0.15))

        candidates: List[Dict[str, Any]] = []

        def add_candidate(
            event: Event,
            reason: str,
            source: str,
            severity_override: Optional[float] = None,
        ):
            candidates.append(
                {
                    "time_start": event.time_start,
                    "time_end": event.time_end,
                    "kind": event.kind,
                    "reason": reason,
                    "source": source,
                    "severity": severity_override if severity_override is not None else event.severity,
                    "score": event.score,
                    "speakers": [event.speaker] if event.speaker else [],
                    "segment_refs": [
                        idx
                        for idx in [event.segment_start_idx, event.segment_end_idx]
                        if idx is not None
                    ],
                    "evidence": event.evidence,
                }
            )

        for event in self._normalize_events((pauses_data or {}).get("events", [])):
            if event.kind in {"long_pause", "post_question_silence"}:
                add_candidate(event, event.kind.replace("_", " "), "pauses")

        for event in self._normalize_events((echoes_data or {}).get("events", [])):
            if event.kind == "echo_burst":
                add_candidate(event, "echo burst", "echoes")

        for event in self._normalize_events((momentum_data or {}).get("events", [])):
            if event.kind in {"stall_zone", "momentum_cliff"}:
                add_candidate(event, event.kind.replace("_", " "), "momentum")

        # QA unanswered questions (optional)
        if qa_data:
            for unanswered in qa_data.get("unanswered_questions", []):
                start = float(unanswered.get("start", 0.0))
                end = float(unanswered.get("end", start))
                event = Event(
                    event_id=generate_event_id(
                        transcript_hash, "unanswered_question", None, None, start, end
                    ),
                    kind="unanswered_question",
                    time_start=start,
                    time_end=end,
                    speaker=unanswered.get("speaker"),
                    segment_start_idx=unanswered.get("segment_idx"),
                    segment_end_idx=unanswered.get("segment_idx"),
                    severity=0.5,
                    score=0.5,
                    evidence=[
                        {
                            "source": "qa_analysis",
                            "feature": "unanswered_question",
                            "value": True,
                        }
                    ],
                    links=[
                        {"type": "segment", "idx": unanswered.get("segment_idx")}
                    ]
                    if unanswered.get("segment_idx") is not None
                    else [],
                )
                add_candidate(event, "unanswered question", "qa_analysis")

        # Merge candidates into spans
        candidates.sort(key=lambda c: c["time_start"])
        spans = []
        current = None
        for candidate in candidates:
            if current is None:
                current = {
                    "start": candidate["time_start"],
                    "end": candidate["time_end"],
                    "candidates": [candidate],
                }
                continue
            if candidate["time_start"] <= current["end"] + merge_seconds:
                current["end"] = max(current["end"], candidate["time_end"])
                current["candidates"].append(candidate)
            else:
                spans.append(current)
                current = {
                    "start": candidate["time_start"],
                    "end": candidate["time_end"],
                    "candidates": [candidate],
                }
        if current:
            spans.append(current)

        moments = []
        for span in spans:
            span_candidates = span["candidates"]
            sources = {c["source"] for c in span_candidates}
            speakers = set()
            segment_refs = set()
            for c in span_candidates:
                speakers.update([s for s in c["speakers"] if s])
                segment_refs.update(c["segment_refs"])

            base_score = sum(
                weight_map.get(c["kind"], 0.2) * c["severity"]
                for c in span_candidates
            )
            diversity = diversity_bonus * max(0, len(sources) - 1)
            multi_speaker = multi_speaker_bonus if len(speakers) > 1 else 0.0
            score = float(base_score + diversity + multi_speaker)

            # Build explanation
            evidence_items = []
            for c in sorted(span_candidates, key=lambda x: x["severity"], reverse=True):
                evidence_items.append(
                    {
                        "reason": c["reason"],
                        "source": c["source"],
                        "severity": c["severity"],
                        "evidence": c["evidence"],
                    }
                )

            moments.append(
                {
                    "time_start": span["start"],
                    "time_end": span["end"],
                    "score": score,
                    "sources": sorted(sources),
                    "speakers": sorted(speakers),
                    "segment_refs": sorted(segment_refs),
                    "evidence": evidence_items[:3],
                }
            )

        # Rank
        moments.sort(key=lambda m: m["score"], reverse=True)
        moments = moments[:top_n]

        max_score = max([m["score"] for m in moments], default=1.0)
        events: List[Event] = []
        for rank, moment in enumerate(moments, start=1):
            segment_start = moment["segment_refs"][0] if moment["segment_refs"] else None
            segment_end = moment["segment_refs"][-1] if moment["segment_refs"] else None
            events.append(
                Event(
                    event_id=generate_event_id(
                        transcript_hash,
                        "moment",
                        segment_start,
                        segment_end,
                        moment["time_start"],
                        moment["time_end"],
                    ),
                    kind="moment",
                    time_start=moment["time_start"],
                    time_end=moment["time_end"],
                    speaker=None,
                    segment_start_idx=segment_start,
                    segment_end_idx=segment_end,
                    severity=min(1.0, moment["score"] / max_score),
                    score=moment["score"],
                    evidence=moment["evidence"],
                    links=[
                        {"type": "segment", "idx": idx}
                        for idx in moment["segment_refs"]
                    ],
                )
            )
            moment["rank"] = rank

        stats = {
            "moment_count": len(events),
            "top_n": top_n,
        }

        return {
            "events": events,
            "stats": stats,
            "moments": moments,
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
            momentum_result = context.get_analysis_result("momentum")
            qa_result = context.get_analysis_result("qa_analysis")

            results = self.analyze(
                context.get_segments(),
                context.get_speaker_map(),
                pauses_data=pauses_result,
                echoes_data=echoes_result,
                momentum_data=momentum_result,
                qa_data=qa_result,
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
        moments: List[Dict[str, Any]] = results.get("moments", [])

        save_events_json(events, output_structure, "moments.events.json")
        save_json(stats, str(output_structure.global_data_dir / "moments.stats.json"))

        if moments:
            save_csv(
                [
                    [
                        m.get("rank"),
                        m.get("score"),
                        m.get("time_start"),
                        m.get("time_end"),
                        ", ".join(m.get("speakers", [])),
                    ]
                    for m in moments
                ],
                str(output_structure.global_data_dir / "moments.csv"),
                header=["rank", "score", "time_start", "time_end", "speakers"],
            )

        if moments and getattr(self.config, "write_markdown", False):
            lines = ["# Moments Worth Revisiting\n"]
            for moment in moments:
                lines.append(
                    f"- #{moment.get('rank')} {moment.get('time_start'):.1f}-{moment.get('time_end'):.1f}s "
                    f"(score {moment.get('score'):.2f})"
                )
            md_path = output_structure.global_data_dir / "moments.md"
            write_text(md_path, "\n".join(lines))

        if events:
            xs = [e.time_start for e in events]
            ys = [e.score or e.severity for e in events]
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_MOMENTS_TIMELINE,
                module=self.module_name,
                name="moments_timeline",
                scope="global",
                chart_intent="line_timeseries",
                title="Moments Timeline",
                x_label="Time (seconds)",
                y_label="Score",
                markers=True,
                series=[{"name": "Moment", "x": xs, "y": ys}],
            )
            output_service.save_chart(spec, chart_type="timeline")

        output_service.save_summary(stats, {}, analysis_metadata={})
