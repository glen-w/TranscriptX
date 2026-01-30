"""Summary analysis package."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast
import json
import time

from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.analysis.highlights.core import (  # type: ignore[import-untyped]
    compute_highlights,
)
from transcriptx.core.analysis.summary.core import (  # type: ignore[import-untyped]
    compute_summary,
)
from transcriptx.core.analysis.insights_normalization import (  # type: ignore[import-untyped]
    normalize_segments,
)
from transcriptx.core.utils.logger import get_logger  # type: ignore[import-untyped]
from transcriptx.core.utils.module_result import (  # type: ignore[import-untyped]
    build_module_result,
    capture_exception,
    now_iso,
)
from transcriptx.core.analysis.common import (  # type: ignore[import-untyped]
    log_analysis_start,
    log_analysis_complete,
    log_analysis_error,
)
from transcriptx.core.output.output_service import (  # type: ignore[import-untyped]
    create_output_service,
)
from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]
from transcriptx.core.presentation import (
    build_md_provenance,
    format_segment_anchor_md,
    render_intensity_line,
    render_no_signal_md,
    render_provenance_footer_md,
)

logger = get_logger()


class SummaryAnalysis(AnalysisModule):
    """Executive brief summary derived from highlights."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "summary"

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        config = get_config()
        normalized = normalize_segments(segments, context=None, transcript_key="unknown")
        highlights = compute_highlights(normalized, config.analysis.highlights)
        return compute_summary(highlights, normalized, config.analysis.summary)

    def run_from_context(self, context: Any) -> Dict[str, Any]:
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
            highlights_result, highlights_source = _resolve_highlights(
                context, normalized, config
            )
            summary_payload = compute_summary(
                highlights_result, normalized, config.analysis.summary
            )

            summary_payload.update(
                {
                    "schema_version": 1,
                    "schema_id": "transcriptx.summary.v1",
                    "schema_url": None,
                    "module": self.module_name,
                    "transcript_key": context.get_transcript_key(),
                    "run_id": context.get_run_id(),
                    "transcript_file_id": _extract_transcript_file_id(
                        context.get_segments()
                    ),
                    "transcript_path_rel": None,
                    "scope": "global",
                    "generated_at": now_iso(),
                    "inputs": {
                        "used_highlights": bool(highlights_result),
                        "highlights_source": highlights_source,
                        "used_sentiment": bool(context.get_analysis_result("sentiment")),
                        "used_emotion": bool(context.get_analysis_result("emotion")),
                    },
                }
            )

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            output_service.save_data(summary_payload, "summary", format_type="json")
            markdown = render_summary_markdown(summary_payload)
            output_service.save_text(markdown, "summary", ext=".md")

            context.store_analysis_result(self.module_name, summary_payload)
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
                payload=summary_payload,
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


def _resolve_highlights(
    context: Any, normalized: List[Dict[str, Any]], config: Any
) -> tuple[Dict[str, Any], str]:
    summary_cfg = config.analysis.summary
    highlights_cfg = config.analysis.highlights
    highlights_result = context.get_analysis_result("highlights")
    if isinstance(highlights_result, dict):
        return highlights_result, "context"

    base_name = context.get_base_name()
    highlights_path = (
        Path(context.get_transcript_dir())
        / "highlights"
        / "data"
        / "global"
        / f"{base_name}_highlights.json"
    )
    if highlights_path.exists():
        with open(highlights_path, "r", encoding="utf-8") as handle:
            return cast(Dict[str, Any], json.load(handle)), "artifact"

    if summary_cfg.require_highlights:
        raise ValueError(
            "Summary requires highlights, but no highlights results or artifacts were found."
        )

    if summary_cfg.compute_highlights_if_missing:
        return (
            cast(Dict[str, Any], compute_highlights(normalized, highlights_cfg)),
            "computed_by_summary",
        )

    if summary_cfg.allow_degraded:
        return {}, "missing"

    raise ValueError(
        "Highlights missing and compute_highlights_if_missing is disabled."
    )


def render_summary_markdown(summary_payload: Dict[str, Any]) -> str:
    inputs = summary_payload.get("inputs", {})
    highlights_source = inputs.get("highlights_source")
    sentiment_flag = "✅" if inputs.get("used_sentiment") else "❌"
    emotion_flag = "✅" if inputs.get("used_emotion") else "❌"
    highlights_flag = "✅" if inputs.get("used_highlights") else "❌"

    overview = summary_payload.get("overview", {})
    key_themes = summary_payload.get("key_themes", {}).get("bullets", [])
    tension_points = summary_payload.get("tension_points", {}).get("bullets", [])
    commitments = summary_payload.get("commitments", {}).get("items", [])

    has_content = bool(
        overview.get("paragraph")
        or key_themes
        or tension_points
        or commitments
    )
    intensity_value = None
    if has_content:
        intensity_value = min(1.0, len(tension_points) / 3) if tension_points else 0.0

    lines = ["# Executive Summary", ""]
    lines.append(render_intensity_line("Summary", intensity_value))
    lines.append("")
    lines.append(
        f"Generated from: highlights {highlights_flag} / sentiment {sentiment_flag} / emotion {emotion_flag}"
    )
    if highlights_source == "computed_by_summary":
        lines.append("Note: Highlights were computed implicitly by the summary module for this run.")
    lines.append("")

    if not has_content:
        lines.append(
            render_no_signal_md(
                "Summary signals did not meet the minimum thresholds for this run.",
                looked_for=["key themes", "tension points", "commitments"],
            ).rstrip()
        )
        lines.append("")
        prov = build_md_provenance("summary", payload=summary_payload)
        lines.append(render_provenance_footer_md(prov).rstrip())
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Overview")
    lines.append(overview.get("paragraph", ""))
    lines.append("")

    lines.append("## Key themes")
    for bullet in key_themes:
        lines.append(f"- {bullet.get('text', '')}")
    lines.append("")

    lines.append("## Tension points")
    for bullet in tension_points:
        anchor = bullet.get("anchor_quote", {})
        lines.append(f"- {bullet.get('text', '')}")
        if anchor:
            refs = anchor.get("segment_refs") or {}
            anchor_md = format_segment_anchor_md(
                start=anchor.get("start"),
                end=anchor.get("end"),
                speaker=anchor.get("speaker"),
                segment_indexes=refs.get("segment_indexes") or [],
                segment_db_ids=refs.get("segment_db_ids") or [],
                segment_uuids=refs.get("segment_uuids") or [],
            )
            lines.append(
                f"  - **{anchor.get('speaker','')}**: {anchor.get('quote','')} {anchor_md}"
            )
    lines.append("")

    lines.append("## Commitments / Next steps")
    for item in commitments:
        owner = item.get("owner_display", "")
        action = item.get("action", "")
        lines.append(f"- **{owner}**: {action}")
    lines.append("")

    prov = build_md_provenance("summary", payload=summary_payload)
    lines.append(render_provenance_footer_md(prov).rstrip())
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _extract_transcript_file_id(segments: List[Dict[str, Any]]) -> Optional[int]:
    for segment in segments:
        value = segment.get("transcript_file_id")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None
