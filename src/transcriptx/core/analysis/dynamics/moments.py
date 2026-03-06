"""
Moments analysis module for TranscriptX.

Aggregates candidate events from pauses, echoes, momentum, and qa_analysis into
merged spans ("moments"), ranks them by score, and enriches each moment with
transcript-based revisit hooks (segment_refs, speakers, excerpt). Outputs
include JSON/CSV/stats, a timeline chart (scatter by time, marker size = duration),
and an explainable score_breakdown per moment.

How to interpret:
- Moments are time intervals [time_start, time_end] worth revisiting.
- The timeline chart shows them in chronological order; marker size reflects duration.
- score_breakdown: score_base (from event kinds/severity), diversity_bonus (multiple
  sources), multi_speaker_bonus (multiple speakers in span), score_total.
- segment_refs are transcript segment indices overlapping the span (for "click to segment").
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.models.events import Event, generate_event_id
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.io import save_csv, save_json
from transcriptx.core.utils.viz_ids import VIZ_MOMENTS_TIMELINE
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import ScatterSpec, ScatterSeries

# Default weight for candidate kinds not in weight_map
DEFAULT_WEIGHT = 0.2


def _overlapping_segments(
    segments: List[Dict[str, Any]], t0: float, t1: float
) -> List[Tuple[int, Dict[str, Any]]]:
    """Return (index, segment) for each segment overlapping [t0, t1].

    Overlap condition: seg.start < t1 and seg.end > t0.
    Uses 'start'/'end' or 'start_time'/'end_time' on segment dicts.
    """
    out: List[Tuple[int, Dict[str, Any]]] = []
    for i, seg in enumerate(segments):
        start = seg.get("start", seg.get("start_time"))
        end = seg.get("end", seg.get("end_time"))
        if start is None or end is None:
            continue
        if start < t1 and end > t0:
            out.append((i, seg))
    return out


class MomentsAnalysis(AnalysisModule):
    """Aggregate events into ranked moments with transcript enrichment and score breakdown."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "moments"
        self.config = get_config().analysis.moments

    def _build_timeline_spec(
        self, moments: List[Dict[str, Any]]
    ) -> Optional[ScatterSpec]:
        """Build a scatter timeline spec from moments (time-sorted, markers only, size = duration).

        Callers should pass moments sorted by time_start so the chart is chronological.
        Preserves viz_id and chart slug for registry compatibility.
        """
        if not moments:
            return None
        moments_sorted = sorted(moments, key=lambda m: m["time_start"])
        xs = [m["time_start"] for m in moments_sorted]
        x_display, x_label = time_axis_display(xs)
        ys = [m["score"] for m in moments_sorted]
        durations = [max(0.0, m["time_end"] - m["time_start"]) for m in moments_sorted]
        # Scale marker size: normalize to a reasonable range (e.g. 20–200)
        max_dur = max(durations) if durations else 1.0
        if max_dur <= 0:
            max_dur = 1.0
        sizes = [20.0 + 180.0 * (d / max_dur) for d in durations]
        return ScatterSpec(
            viz_id=VIZ_MOMENTS_TIMELINE,
            module=self.module_name,
            name="moments_timeline",
            scope="global",
            chart_intent="scatter_events",
            title="Moments Timeline",
            x_label=x_label,
            y_label="Score",
            notes="Marker size = duration.",
            series=[
                ScatterSeries(
                    name="Moment",
                    x=x_display,
                    y=ys,
                    marker={"size": sizes},
                )
            ],
            mode="markers",
        )

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
        max_span_seconds = float(getattr(self.config, "max_span_seconds", 120.0))
        weight_map = getattr(self.config, "weight_map", {}) or {}
        diversity_bonus = float(getattr(self.config, "diversity_bonus", 0.2))
        multi_speaker_bonus = float(getattr(self.config, "multi_speaker_bonus", 0.15))
        excerpt_max_chars = int(getattr(self.config, "excerpt_max_chars", 200))
        excerpt_max_segments = int(getattr(self.config, "excerpt_max_segments", 2))

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
                    "severity": (
                        severity_override
                        if severity_override is not None
                        else event.severity
                    ),
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
                    links=(
                        [{"type": "segment", "idx": unanswered.get("segment_idx")}]
                        if unanswered.get("segment_idx") is not None
                        else []
                    ),
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

        # Chain-merge prevention: split spans exceeding max_span_seconds
        expanded_spans: List[Dict[str, Any]] = []
        for span in spans:
            start, end = span["start"], span["end"]
            span_candidates = span["candidates"]
            if (end - start) <= max_span_seconds:
                expanded_spans.append(span)
                continue
            # Split into time chunks of max_span_seconds
            t = start
            while t < end:
                chunk_end = min(t + max_span_seconds, end)
                chunk_candidates = [
                    c
                    for c in span_candidates
                    if c["time_start"] < chunk_end and c["time_end"] > t
                ]
                if chunk_candidates:
                    expanded_spans.append(
                        {
                            "start": t,
                            "end": chunk_end,
                            "candidates": chunk_candidates,
                        }
                    )
                t = chunk_end

        moments = []
        for span in expanded_spans:
            span_candidates = span["candidates"]
            t0, t1 = span["start"], span["end"]

            # Enrichment from transcript (before scoring): segment_refs, speakers, excerpt
            candidate_refs = set()
            for c in span_candidates:
                candidate_refs.update(c["segment_refs"])
            segment_refs: List[int] = []
            speakers_list: List[str] = []
            excerpt = ""
            if segments:
                overlapping = _overlapping_segments(segments, t0, t1)
                if overlapping:
                    segment_refs = sorted(idx for idx, _ in overlapping)
                    speakers_set = set()
                    texts: List[str] = []
                    for idx, seg in overlapping[:excerpt_max_segments]:
                        sp = seg.get("speaker")
                        if sp and str(sp).strip():
                            speakers_set.add(str(sp).strip())
                        txt = seg.get("text") or ""
                        if isinstance(txt, str) and txt.strip():
                            texts.append(txt.strip())
                    speakers_list = sorted(speakers_set)
                    if texts:
                        joined = " ".join(texts)
                        excerpt = joined[:excerpt_max_chars] + (
                            "..." if len(joined) > excerpt_max_chars else ""
                        )
            if not segment_refs:
                segment_refs = sorted(candidate_refs)
            if not speakers_list:
                speakers_list = sorted(
                    s for c in span_candidates for s in c["speakers"] if s
                )

            # sources_included: use "unknown" when source missing so diversity is stable
            sources_included = set(
                (c.get("source") or "unknown") for c in span_candidates
            )

            # Score breakdown
            per_kind: Dict[str, float] = {}
            for c in span_candidates:
                kind = c["kind"]
                w = weight_map.get(kind, DEFAULT_WEIGHT)
                contrib = w * (c.get("severity") or 0.0)
                per_kind[kind] = per_kind.get(kind, 0.0) + contrib
            score_base = sum(per_kind.values())
            score_diversity_bonus = diversity_bonus * max(0, len(sources_included) - 1)
            score_multi_speaker_bonus = (
                multi_speaker_bonus if len(speakers_list) > 1 else 0.0
            )
            score_total = float(
                score_base + score_diversity_bonus + score_multi_speaker_bonus
            )
            score_breakdown = {
                "score_total": score_total,
                "score_base": score_base,
                "score_diversity_bonus": score_diversity_bonus,
                "score_multi_speaker_bonus": score_multi_speaker_bonus,
                "per_kind_contributions": per_kind,
                "sources_included": sorted(sources_included),
                "event_count": len(span_candidates),
            }

            # Build explanation (evidence)
            evidence_items = []
            for c in sorted(
                span_candidates, key=lambda x: x.get("severity") or 0, reverse=True
            ):
                evidence_items.append(
                    {
                        "reason": c.get("reason", ""),
                        "source": c.get("source") or "unknown",
                        "severity": c.get("severity", 0),
                        "evidence": c.get("evidence", []),
                    }
                )

            moments.append(
                {
                    "time_start": t0,
                    "time_end": t1,
                    "score": score_total,
                    "sources": sorted(sources_included),
                    "speakers": speakers_list,
                    "segment_refs": segment_refs,
                    "segment_count": len(segment_refs),
                    "excerpt": excerpt,
                    "evidence": evidence_items[:3],
                    "score_breakdown": score_breakdown,
                }
            )

        # Rank
        moments.sort(key=lambda m: m["score"], reverse=True)
        moments = moments[:top_n]

        max_score = max([m["score"] for m in moments], default=1.0)
        if max_score <= 0:
            max_score = 1.0
        events: List[Event] = []
        for rank, moment in enumerate(moments, start=1):
            seg_refs = moment["segment_refs"]
            segment_start = seg_refs[0] if seg_refs else None
            segment_end = seg_refs[-1] if seg_refs else None
            severity = min(1.0, moment["score"] / max_score)
            evidence_with_breakdown = list(moment.get("evidence", []))
            if moment.get("score_breakdown"):
                evidence_with_breakdown.append(
                    {"source": "moments", "score_breakdown": moment["score_breakdown"]}
                )
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
                    severity=severity,
                    score=moment["score"],
                    evidence=evidence_with_breakdown,
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
            # Full moments list with enrichment and score_breakdown
            save_json(
                moments,
                str(output_structure.global_data_dir / "moments.moments.json"),
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

        spec = self._build_timeline_spec(moments)
        if spec is not None:
            output_service.save_chart(spec, chart_type="timeline")

        output_service.save_summary(stats, {}, analysis_metadata={})
