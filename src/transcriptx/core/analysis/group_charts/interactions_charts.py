"""Interactions: curated session bars plus pooled additive role counts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import chart_artifact_paths
from transcriptx.core.analysis.group_charts.generic_field_allowlists import (
    allowed_numeric_keys_for_generic_agg,
)
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.output_service import (
    GroupChartOutputService,
)
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.viz.specs import BarCategoricalSpec

_COUNT_FIELDS = (
    "interruptions_initiated",
    "interruptions_received",
    "responses_initiated",
    "responses_received",
)


def _parse_interactions_pooled(
    outcome: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    p = outcome.get("interactions_pooled")
    if not isinstance(p, dict):
        return None
    if p.get("schema_version") != 1:
        return None
    speakers = p.get("speakers")
    if not isinstance(speakers, list) or not speakers:
        return None
    out: List[Dict[str, Any]] = []
    for row in speakers:
        if not isinstance(row, dict):
            continue
        cid = row.get("canonical_speaker_id")
        if not isinstance(cid, int):
            continue
        out.append(row)
    return out or None


def _any_positive_counts(speakers: List[Dict[str, Any]]) -> bool:
    for s in speakers:
        for k in _COUNT_FIELDS:
            v = s.get(k)
            if isinstance(v, (int, float)) and int(v) > 0:
                return True
    return False


def _top_speakers_by_metric(
    speakers: List[Dict[str, Any]], metric: str, limit: int = 15
) -> Tuple[List[str], List[float]]:
    scored: List[Tuple[float, str, int]] = []
    for s in speakers:
        label = str(s.get("display_name") or f"speaker_{s.get('canonical_speaker_id')}")
        cid = int(s.get("canonical_speaker_id") or 0)
        val = float(s.get(metric) or 0)
        scored.append((val, label, cid))
    scored.sort(key=lambda t: (-t[0], t[2], t[1]))
    top = [t for t in scored if t[0] > 0][:limit]
    if not top:
        return [], []
    return [t[1] for t in top], [t[0] for t in top]


class InteractionsGroupChartGenerator:
    """Session bars via curated generic; pooled charts from ``interactions_pooled`` only."""

    agg_id = "interactions"

    def __init__(self) -> None:
        allow = allowed_numeric_keys_for_generic_agg("interactions")
        self._session = GenericNumericGroupChartGenerator(
            "interactions",
            flatten_nested=True,
            max_charts=10,
            allowed_numeric_keys=allow,
        )

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        if self._session.can_generate(outcome):
            return True
        speakers = _parse_interactions_pooled(outcome)
        if not speakers:
            return False
        return _any_positive_counts(speakers)

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        paths: List[Path] = []
        sub = self._session.generate(ctx, outcome)
        if sub is not None:
            paths.extend(sub)

        speakers = _parse_interactions_pooled(outcome)
        if speakers and _any_positive_counts(speakers):
            virtual = build_group_virtual_transcript_path(
                ctx.group_run_root, self.agg_id
            )
            svc = GroupChartOutputService(
                virtual_transcript_path=virtual,
                module_name=self.agg_id,
                output_dir=str(ctx.group_run_root.resolve()),
                run_id=ctx.group_run_id,
                agg_id=self.agg_id,
                group_uuid=ctx.group_uuid,
            )
            for metric, viz_id, title_part in (
                (
                    "interruptions_initiated",
                    "group.interactions.pooled.interruptions_initiated.global",
                    "interruptions initiated (pooled)",
                ),
                (
                    "interruptions_received",
                    "group.interactions.pooled.interruptions_received.global",
                    "interruptions received (pooled)",
                ),
            ):
                labels, vals = _top_speakers_by_metric(speakers, metric)
                if not labels:
                    continue
                safe = metric
                svc.save_chart(
                    BarCategoricalSpec(
                        viz_id=viz_id,
                        module=self.agg_id,
                        name=f"interactions_pooled_{safe}"[:80],
                        scope="global",
                        chart_intent="bar_categorical",
                        title=f"Group pooled — {title_part}",
                        x_label="Speaker",
                        y_label="Count",
                        categories=labels,
                        values=vals,
                    ),
                    chart_type="bar",
                )
            paths.extend(chart_artifact_paths(svc))

        return paths or None
