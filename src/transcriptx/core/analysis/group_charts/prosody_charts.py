"""
Group aggregate charts for prosody (prefix-filtered session bars + temporal overlay).

Session rows use flat keys allowed by ``_aggregate_prosody`` (``prosody.*``,
``voice_features.*``, ``voice_charts_core.*``); see aggregation registry.
Temporal overlay reads ``{base}_prosody_overlay_segments.v1.json`` — see
``docs/groups/group_charts_prosody_temporal_contract.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.helpers import (
    make_group_output_service,
    SESSION_META_KEYS,
    chart_artifact_paths,
    member_session_label,
    merge_numeric_keys_from_session_rows,
    session_row_label,
)
from transcriptx.core.analysis.group_charts.overlay_series import (
    cap_per_transcript_results_for_overlay,
)
from transcriptx.core.analysis.voice.prosody_overlay_segments import (
    PROSODY_OVERLAY_Y_FIELD,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec

# Mirrors allow_prefixes in aggregation ``_aggregate_prosody``.
_PROSODY_KEY_PREFIXES: tuple[str, ...] = (
    "prosody.",
    "voice_features.",
    "voice_charts_core.",
)
_PROSODY_EXCLUDE = SESSION_META_KEYS | {"raw"}
_MAX_SESSION_BAR_CHARTS = 10

_PREFIX = "Group aggregate (prosody summary by session, not time series)"


def _allowed_prosody_key(key: str) -> bool:
    return any(key.startswith(p) for p in _PROSODY_KEY_PREFIXES)


def _prosody_chart_keys(session_rows: List[Dict[str, Any]]) -> List[str]:
    keys = merge_numeric_keys_from_session_rows(
        session_rows,
        exclude=_PROSODY_EXCLUDE,
        flatten_dict_one_level=False,
    )
    filtered = [k for k in keys if _allowed_prosody_key(k)]
    return filtered[:_MAX_SESSION_BAR_CHARTS]


def _prosody_overlay_artifact_path(result: PerTranscriptResult) -> Path:
    base = get_canonical_base_name(result.transcript_path)
    return (
        Path(result.output_dir)
        / "prosody_dashboard"
        / "data"
        / "global"
        / f"{base}_prosody_overlay_segments.v1.json"
    )


def _load_member_prosody_segments(result: PerTranscriptResult) -> List[Dict[str, Any]]:
    path = _prosody_overlay_artifact_path(result)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, dict):
        return []
    if raw.get("schema_version") != 1:
        return []
    if raw.get("y_field") != PROSODY_OVERLAY_Y_FIELD:
        return []
    segs = raw.get("segments")
    if not isinstance(segs, list):
        return []
    return [s for s in segs if isinstance(s, dict)]


def generate_group_prosody_temporal_overlay(
    output_service: GroupChartOutputService,
    per_transcript_results: Sequence[PerTranscriptResult],
    transcript_set: TranscriptSet,
    *,
    title_prefix: Optional[str] = None,
) -> None:
    """Cross-session RMS dB overlay; see ``docs/groups/group_charts_prosody_temporal_contract.md``."""

    def _tp(title: str) -> str:
        if not title_prefix:
            return title
        return f"{title_prefix} — {title}"

    ordered = cap_per_transcript_results_for_overlay(per_transcript_results)
    temporal_series: List[Dict[str, Any]] = []
    for result in ordered:
        segs = _load_member_prosody_segments(result)
        if not segs:
            continue
        sess_label = member_session_label(result, transcript_set)
        pairs: List[tuple[float, float]] = []
        for seg in segs:
            st = seg.get("start")
            yv = seg.get(PROSODY_OVERLAY_Y_FIELD)
            if not isinstance(st, (int, float)) or isinstance(st, bool):
                continue
            if not isinstance(yv, (int, float)) or isinstance(yv, bool):
                continue
            pairs.append((float(st), float(yv)))
        if len(pairs) < 2:
            continue
        pairs.sort(key=lambda p: p[0])
        t0 = pairs[0][0]
        temporal_series.append(
            {
                "name": sess_label,
                "x": [(t - t0) / 60.0 for t, _ in pairs],
                "y": [y for _, y in pairs],
            }
        )

    if temporal_series:
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id="group.prosody.temporal_overlay.global",
                module="prosody",
                name="temporal_overlay",
                scope="global",
                chart_intent="line_timeseries",
                title=_tp(
                    "RMS dB — cross-session overlay, session-relative minutes "
                    "(artifact rms_db; not one continuous timeline)"
                ),
                x_label="Session-relative minutes from first segment",
                y_label="RMS (dB)",
                markers=True,
                series=temporal_series,
            ),
            chart_type="temporal",
        )


class ProsodyGroupChartGenerator:
    """Prefix-filtered prosody session bars + optional temporal overlay."""

    agg_id = "prosody"

    def can_generate(self, outcome: Dict[str, Any]) -> bool:
        session_rows = outcome.get("session_rows") or []
        if len(session_rows) < 1:
            return False
        return len(_prosody_chart_keys(list(session_rows))) > 0

    def generate(
        self, ctx: GroupChartContext, outcome: Dict[str, Any]
    ) -> Optional[List[Path]]:
        session_rows = list(outcome.get("session_rows") or [])
        session_rows.sort(key=lambda r: r.get("order_index", 0))
        keys = _prosody_chart_keys(session_rows)
        if not keys:
            return None

        svc = make_group_output_service(
            ctx, module_name=self.agg_id, agg_id=self.agg_id
        )
        labels = [session_row_label(r, ctx.transcript_set) for r in session_rows]

        for key in keys:
            vals: List[float] = []
            for row in session_rows:
                vals.append(float(row.get(key) or 0))
            if not any(vals):
                continue
            safe_name = key.replace(".", "_")
            svc.save_chart(
                BarCategoricalSpec(
                    viz_id=f"group.{self.agg_id}.session.{safe_name}",
                    module=self.agg_id,
                    name=f"group_session_{safe_name}"[:80],
                    scope="global",
                    chart_intent="bar_categorical",
                    title=f"{_PREFIX} — {key}",
                    x_label="Session",
                    y_label=key,
                    categories=labels,
                    values=vals,
                ),
                chart_type="bar",
            )

        if (
            should_emit_temporal_overlay_charts(self.agg_id, ctx.per_transcript_results)
            and ctx.per_transcript_results
        ):
            generate_group_prosody_temporal_overlay(
                svc,
                ctx.per_transcript_results,
                ctx.transcript_set,
                title_prefix=_PREFIX,
            )

        out = chart_artifact_paths(svc)
        return out or None
