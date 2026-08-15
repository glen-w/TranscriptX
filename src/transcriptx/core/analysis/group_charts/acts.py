"""
Group aggregate charts for dialogue acts.

Families (see ``GROUP_AGGREGATE_CHART_FAMILIES`` in ``registry.py``):

- **aggregate_pie_bar** — pie/bar specs from aggregated session and speaker counts.
- **temporal_overlay** — cross-session act trajectories from member ``*_with_acts.json``.
- **pooled_single_view** — global pie/bar already sum all sessions (audited; see
  ``docs/groups/group_charts_acts_pooled_contract.md``); no separate pooled chart.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from transcriptx.core.analysis.acts.config import get_all_act_types
from transcriptx.core.analysis.acts.output import generate_acts_charts
from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    chart_artifact_paths,
    filter_chartable_speaker_rows,
    member_session_label,
)
from transcriptx.core.analysis.group_charts.overlay_series import (
    cap_per_transcript_results_for_overlay,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils._path_core import get_base_name
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)
from transcriptx.core.viz.specs import LineTimeSeriesSpec
from transcriptx.io import load_transcript
from transcriptx.utils.text_utils import is_analysis_speaker_label


def reconstruct_act_counters(
    session_rows: List[Dict[str, Any]],
    speaker_rows: List[Dict[str, Any]],
) -> Tuple[Counter, Dict[str, Counter]]:
    """Sum act-type columns across sessions; merge speaker rows by canonical id."""
    act_types = set(get_all_act_types())
    global_counter: Counter = Counter()
    for row in session_rows:
        for k, v in row.items():
            if k not in act_types:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                global_counter[k] += int(v)

    by_canon: Dict[Any, Counter] = defaultdict(Counter)
    display_for: Dict[Any, str] = {}
    for row in filter_chartable_speaker_rows(speaker_rows):
        cid = row["canonical_speaker_id"]
        dn = row.get("display_name")
        display_for[cid] = str(dn) if dn is not None else str(cid)
        for k, v in row.items():
            if k not in act_types:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                by_canon[cid][k] += int(v)

    per_display = {display_for[cid]: ctr for cid, ctr in by_canon.items()}
    return global_counter, per_display


def _load_member_acts_segments(result: PerTranscriptResult) -> List[Dict[str, Any]]:
    path = (
        Path(result.output_dir)
        / "acts"
        / "data"
        / "global"
        / f"{get_base_name(result.transcript_path)}_with_acts.json"
    )
    if not path.is_file():
        return []
    data = load_transcript(str(path))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        segs = data.get("segments")
        if isinstance(segs, list):
            return segs
    return []


def generate_group_acts_temporal_overlay(
    output_service: GroupChartOutputService,
    act_counts_global: Dict[str, int],
    act_counts_per_speaker: Dict[str, Counter],
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    *,
    title_prefix: str | None = None,
) -> None:
    """
    Cross-session line overlay; see ``docs/group_charts_acts_temporal_contract.md``.
    """

    def _tp(title: str) -> str:
        if not title_prefix:
            return title
        return f"{title_prefix} — {title}"

    speakers = sorted(
        [s for s in act_counts_per_speaker.keys() if is_analysis_speaker_label(s)]
    )
    if not act_counts_global or not speakers:
        return

    total = sum(act_counts_global.values())
    acts_over_5 = (
        [a for a, c in act_counts_global.items() if c / total > 0.05]
        if total > 0
        else []
    )
    if not acts_over_5:
        return
    act_idx_map = {a: i for i, a in enumerate(acts_over_5)}

    temporal_series: List[Dict[str, Any]] = []
    for result in cap_per_transcript_results_for_overlay(per_transcript_results):
        segs = _load_member_acts_segments(result)
        if not segs:
            continue
        raw_starts = [
            float(s.get("start") or 0)
            for s in segs
            if isinstance(s, dict) and isinstance(s.get("start"), (int, float))
        ]
        t0 = min(raw_starts) if raw_starts else 0.0
        sess_label = member_session_label(result, transcript_set)

        for speaker in speakers:
            times: List[float] = []
            acts_list: List[str] = []
            for seg in segs:
                if not isinstance(seg, dict):
                    continue
                speaker_info = extract_speaker_info(seg)
                if speaker_info is None:
                    continue
                spk = get_speaker_display_name(speaker_info.grouping_key, [seg], segs)
                if spk != speaker:
                    continue
                act = seg.get("dialogue_act", "")
                if act in acts_over_5:
                    acts_list.append(act)
                    st = seg.get("start", 0)
                    if not isinstance(st, (int, float)):
                        st = 0
                    times.append((float(st) - t0) / 60.0)
            y_vals = [act_idx_map[a] for a in acts_list]
            if not y_vals:
                continue
            temporal_series.append(
                {
                    "name": f"{sess_label}: {speaker}",
                    "x": times,
                    "y": y_vals,
                }
            )

    if temporal_series:
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id="group.acts.temporal_overlay.global",
                module="acts",
                name="temporal_overlay",
                scope="global",
                chart_intent="line_timeseries",
                title=_tp(
                    "Dialogue acts over time — cross-session overlay "
                    "(x = minutes from each session start; not a single timeline)"
                ),
                x_label="Minutes from session start (per member run)",
                y_label="Dialogue act (index)",
                markers=True,
                series=temporal_series,
            ),
            chart_type="temporal",
        )


class ActsGroupChartGenerator:
    agg_id = "acts"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        speaker_rows = outcome.get("speaker_rows") or []
        if not session_rows:
            return False
        g, p = reconstruct_act_counters(session_rows, speaker_rows)
        return sum(g.values()) > 0 or any(sum(c.values()) > 0 for c in p.values())

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = outcome.get("session_rows") or []
        speaker_rows = outcome.get("speaker_rows") or []
        global_c, per_spk = reconstruct_act_counters(session_rows, speaker_rows)

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        # Tier 1: empty segment list skips temporal charts inside generate_acts_charts.
        generate_acts_charts(
            svc,
            [],
            dict(global_c),
            per_spk,
            ctx.chart_base_name,
            title_prefix="Group aggregate (summed across sessions)",
            group_aggregate_viz_ids=True,
        )
        if (
            should_emit_temporal_overlay_charts(self.agg_id, ctx.per_transcript_results)
            and ctx.per_transcript_results
        ):
            generate_group_acts_temporal_overlay(
                svc,
                dict(global_c),
                per_spk,
                ctx.per_transcript_results,
                ctx.transcript_set,
                title_prefix="Group aggregate (summed across sessions)",
            )
        return chart_artifact_paths(svc)
