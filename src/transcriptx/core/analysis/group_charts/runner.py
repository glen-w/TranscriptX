"""Single entrypoint: run group aggregate charts for one aggregation outcome."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.registry import GROUP_CHART_REGISTRY
from transcriptx.core.analysis.group_charts.result import GroupChartRunResult
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

_STAGE = "group_chart_generation"


def run_group_aggregate_charts(
    *,
    agg_id: str,
    group_run_root: Path,
    group_run_id: str,
    outcome: Dict[str, Any],
    transcript_set: TranscriptSet,
    group_uuid: Optional[str] = None,
    per_transcript_results: Optional[List[PerTranscriptResult]] = None,
    canonical_speaker_map: Optional[CanonicalSpeakerMap] = None,
    registry: Optional[Dict[str, Any]] = None,
) -> GroupChartRunResult:
    """
    Best-effort chart pass for one aggregation. Never raises to the pipeline caller.
    """
    reg = registry if registry is not None else GROUP_CHART_REGISTRY
    gen = reg.get(agg_id)
    if gen is None:
        return GroupChartRunResult(skipped_reason="no_generator")

    if not gen.can_generate(outcome):
        return GroupChartRunResult(skipped_reason="can_generate_false")

    ctx = GroupChartContext(
        group_run_root=group_run_root.resolve(),
        group_run_id=group_run_id,
        agg_id=agg_id,
        transcript_set=transcript_set,
        group_uuid=group_uuid,
        per_transcript_results=per_transcript_results,
        canonical_speaker_map=canonical_speaker_map,
    )
    chart_generator = f"{gen.__class__.__name__}:{agg_id}"

    try:
        paths = gen.generate(ctx, outcome)
        emitted = list(paths) if paths else []
        return GroupChartRunResult(emitted_paths=emitted, skipped_reason=None)
    except Exception as exc:
        logger.warning(
            "Group chart generation failed for %s: %s",
            agg_id,
            exc,
            exc_info=True,
        )
        warn = build_warning(
            code="GROUP_CHART_FAILED",
            message=str(exc),
            aggregation_key=agg_id,
            details={
                "chart_generator": chart_generator,
                "stage": _STAGE,
                "traceback": traceback.format_exc(),
            },
        )
        return GroupChartRunResult(
            warnings=[warn],
            skipped_reason="chart_failed",
        )
