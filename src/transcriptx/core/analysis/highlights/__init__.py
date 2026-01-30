"""Highlights analysis package."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import time

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.highlights.core import compute_highlights
from transcriptx.core.analysis.insights_normalization import normalize_segments
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.module_result import build_module_result, capture_exception, now_iso
from transcriptx.core.analysis.common import (
    log_analysis_start,
    log_analysis_complete,
    log_analysis_error,
)
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.utils.config import get_config
from transcriptx.core.presentation import (
    build_md_provenance,
    format_segment_anchor_md,
    render_intensity_line,
    render_no_signal_md,
    render_provenance_footer_md,
)

logger = get_logger()


class HighlightsAnalysis(AnalysisModule):
    """Quote-forward highlights and conflict moments."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "highlights"

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        config = get_config()
        normalized = normalize_segments(
            segments, context=None, transcript_key="unknown"
        )
        return compute_highlights(normalized, config.analysis.highlights)

    def run_from_context(self, context) -> Dict[str, Any]:
        started_at = now_iso()
        start_time = time.time()
        try:
            log_analysis_start(self.module_name, context.transcript_path)
            config = get_config()
            normalized = normalize_segments(
                context.get_segments(),
                context=context,
                transcript_key=context.get_transcript_key(),
            )
            results = compute_highlights(normalized, config.analysis.highlights)

            results.update(
                {
                    "module": self.module_name,
                    "transcript_key": context.get_transcript_key(),
                    "run_id": context.get_run_id(),
                    "transcript_file_id": _extract_transcript_file_id(
                        context.get_segments()
                    ),
                    "transcript_path_rel": None,
                    "generated_at": now_iso(),
                    "config_snapshot": _snapshot_highlights_config(
                        config.analysis.highlights
                    ),
                    "inputs": {
                        "used_sentiment": bool(
                            context.get_analysis_result("sentiment")
                        ),
                        "used_emotion": bool(context.get_analysis_result("emotion")),
                    },
                }
            )

            conflict_rows = results.pop("conflict_rows", [])

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self._save_results(results, conflict_rows, output_service)

            context.store_analysis_result(self.module_name, results)
            log_analysis_complete(self.module_name, context.transcript_path)

            finished_at = now_iso()
            duration_seconds = time.time() - start_time
            output_structure = output_service.get_output_structure()
            output_directory = (
                str(output_structure.module_dir)
                if hasattr(output_structure, "module_dir")
                else ""
            )

            module_result = build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=output_service.get_artifacts(),
                metrics={
                    "duration_seconds": duration_seconds,
                    "output_directory": output_directory,
                },
                payload_type="analysis_results",
                payload=results,
            )
            module_result["output_directory"] = output_directory
            return module_result
        except Exception as exc:
            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            finished_at = now_iso()
            duration_seconds = time.time() - start_time
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=[],
                metrics={"duration_seconds": duration_seconds},
                payload_type="analysis_results",
                payload={},
                error=capture_exception(exc),
            )

    def _save_results(
        self,
        results: Dict[str, Any],
        conflict_rows: List[Dict[str, Any]],
        output_service,
    ) -> None:
        output_service.save_data(results, "highlights", format_type="json")
        markdown = render_highlights_markdown(results)
        output_service.save_text(markdown, "highlights", ext=".md")
        if (
            conflict_rows
            and get_config().analysis.highlights.output.write_conflict_csv
        ):
            output_service.save_data(conflict_rows, "conflict_events", format_type="csv")


def render_highlights_markdown(results: Dict[str, Any]) -> str:
    sections = results.get("sections", {})
    cold_open = sections.get("cold_open", {})
    conflict = sections.get("conflict_points", {})
    phrases = sections.get("emblematic_phrases", {}).get("phrases", [])

    def _anchor_for_quote(item: Dict[str, Any]) -> str:
        refs = item.get("segment_refs") or {}
        return format_segment_anchor_md(
            start=item.get("start"),
            end=item.get("end"),
            speaker=item.get("speaker"),
            segment_indexes=refs.get("segment_indexes") or [],
            segment_db_ids=refs.get("segment_db_ids") or [],
            segment_uuids=refs.get("segment_uuids") or [],
        )

    scores: List[float] = []
    for item in cold_open.get("items", []):
        score = (item.get("score") or {}).get("total")
        if score is not None:
            scores.append(float(score))
    for event in conflict.get("events", []):
        anchor = event.get("anchor_quote") or {}
        score = (anchor.get("score") or {}).get("total")
        if score is not None:
            scores.append(float(score))
    intensity_value = max(scores) if scores else None

    lines = ["# Highlights", ""]
    lines.append(render_intensity_line("Highlights", intensity_value))
    lines.append("")

    has_quotes = bool(cold_open.get("items") or conflict.get("events"))
    has_phrases = bool(phrases)
    if not has_quotes and not has_phrases:
        lines.append(
            render_no_signal_md(
                "No standout quotes or conflict spikes passed the current thresholds.",
                looked_for=["high-intensity quotes", "conflict windows", "emblematic phrases"],
            ).rstrip()
        )
        lines.append("")
        prov = build_md_provenance("highlights", payload=results)
        lines.append(render_provenance_footer_md(prov).rstrip())
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Cold open")
    for item in cold_open.get("items", []):
        anchor = _anchor_for_quote(item)
        lines.append(
            f"- **{item.get('speaker','')}**: {item.get('quote','')} {anchor}"
        )
    lines.append("")

    lines.append("## Conflict points")
    for event in conflict.get("events", []):
        anchor = event.get("anchor_quote") or {}
        quote = anchor.get("quote", "")
        speaker = anchor.get("speaker", "")
        anchor_md = _anchor_for_quote(anchor) if anchor else ""
        suffix = f" {anchor_md}" if anchor_md else ""
        lines.append(f"- **{speaker}**: {quote}{suffix}")
    lines.append("")

    lines.append("## Emblematic phrases")
    for phrase in phrases:
        lines.append(f"- {phrase.get('phrase','')}")
    lines.append("")

    prov = build_md_provenance("highlights", payload=results)
    lines.append(render_provenance_footer_md(prov).rstrip())
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _snapshot_highlights_config(cfg: Any) -> Dict[str, Any]:
    return {
        "counts": {
            "cold_open_quotes": cfg.counts.cold_open_quotes,
            "total_highlights": cfg.counts.total_highlights,
            "conflict_windows": cfg.counts.conflict_windows,
            "emblematic_phrases": cfg.counts.emblematic_phrases,
        },
        "thresholds": {
            "conflict_spike_percentile": cfg.thresholds.conflict_spike_percentile,
            "min_gap_seconds": cfg.thresholds.min_gap_seconds,
            "min_quote_words": cfg.thresholds.min_quote_words,
            "max_quote_words": cfg.thresholds.max_quote_words,
            "max_consecutive_per_speaker": cfg.thresholds.max_consecutive_per_speaker,
            "min_phrase_len": cfg.thresholds.min_phrase_len,
            "max_phrase_len": cfg.thresholds.max_phrase_len,
            "min_phrase_frequency": cfg.thresholds.min_phrase_frequency,
        },
        "weights": {
            "intensity": cfg.weights.intensity,
            "conflict": cfg.weights.conflict,
            "uniqueness": cfg.weights.uniqueness,
            "keyword_richness": cfg.weights.keyword_richness,
        },
        "merge_adjacent": {
            "enabled": cfg.merge_adjacent.enabled,
            "max_gap_seconds": cfg.merge_adjacent.max_gap_seconds,
            "max_segments": cfg.merge_adjacent.max_segments,
        },
        "cold_open": {
            "window_seconds": cfg.cold_open.window_seconds,
            "window_policy": cfg.cold_open.window_policy,
        },
        "output": {
            "write_conflict_csv": cfg.output.write_conflict_csv,
        },
    }


def _extract_transcript_file_id(segments: List[Dict[str, Any]]) -> Optional[int]:
    for segment in segments:
        if segment.get("transcript_file_id") is not None:
            return int(segment.get("transcript_file_id"))
    return None
