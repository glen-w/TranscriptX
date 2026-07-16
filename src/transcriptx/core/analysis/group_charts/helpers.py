"""Shared helpers for group chart generators."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.output_service import (
    GroupChartOutputService,
)
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.utils.text_utils import is_eligible_named_speaker

SESSION_META_KEYS: Set[str] = {
    "transcript_id",
    "order_index",
    "run_relpath",
    "session_label",
    "session_path",
    "transcript_path",
}

SPEAKER_META_KEYS: Set[str] = {
    "canonical_speaker_id",
    "display_name",
    "speaker_key",
}


def make_group_output_service(
    ctx: GroupChartContext,
    *,
    module_name: str,
    agg_id: str,
) -> GroupChartOutputService:
    """Construct GroupChartOutputService with the canonical group-run mapping."""
    return GroupChartOutputService(
        virtual_transcript_path=build_group_virtual_transcript_path(
            ctx.group_run_root, agg_id
        ),
        module_name=module_name,
        output_dir=str(ctx.group_run_root.resolve()),
        run_id=ctx.group_run_id,
        agg_id=agg_id,
        group_uuid=ctx.group_uuid,
    )


def filter_chartable_speaker_rows(
    rows: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Reuse transcript-level eligibility for per-speaker group charts."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        dn = row.get("display_name")
        cid = row.get("canonical_speaker_id")
        if is_eligible_named_speaker(
            str(dn) if dn is not None else None,
            str(cid) if cid is not None else None,
        ):
            out.append(row)
    return out


def session_row_label(row: Dict[str, Any], transcript_set: TranscriptSet) -> str:
    """Short label for session-level bar charts."""
    if row.get("session_label"):
        return str(row["session_label"])
    tid = row.get("transcript_id")
    if tid is not None:
        return str(tid)[:24]
    return f"session_{row.get('order_index', '?')}"


def iter_numeric_fields(
    row: Dict[str, Any],
    *,
    exclude: Set[str],
    flatten_dict_one_level: bool = False,
) -> List[Tuple[str, float]]:
    """Collect (name, value) pairs suitable for bar charts."""
    found: List[Tuple[str, float]] = []
    for k, v in row.items():
        if k in exclude:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            found.append((k, float(v)))
        elif flatten_dict_one_level and isinstance(v, dict):
            for sk, sv in v.items():
                if isinstance(sv, bool):
                    continue
                if isinstance(sv, (int, float)):
                    found.append((f"{k}.{sk}", float(sv)))
    return found


def merge_numeric_keys_from_session_rows(
    session_rows: List[Dict[str, Any]],
    *,
    exclude: Set[str],
    flatten_dict_one_level: bool = False,
) -> List[str]:
    keys: Set[str] = set()
    for row in session_rows:
        for name, _ in iter_numeric_fields(
            row,
            exclude=exclude,
            flatten_dict_one_level=flatten_dict_one_level,
        ):
            keys.add(name)
    return sorted(keys)


def chart_artifact_paths(svc: GroupChartOutputService) -> List[Path]:
    """Paths to chart files (.png / .html) recorded on a group chart output service."""
    return [
        Path(str(a["path"]))
        for a in svc._artifacts
        if a.get("path") and Path(str(a["path"])).suffix.lower() in {".png", ".html"}
    ]


def member_session_label(
    result: PerTranscriptResult,
    transcript_set: TranscriptSet,
) -> str:
    """Short label for a member transcript in cross-session overlays (e.g. S1 stem)."""
    ids = transcript_set.transcript_ids
    try:
        idx = ids.index(result.transcript_path) + 1
    except ValueError:
        idx = result.order_index + 1
    stem = Path(result.transcript_path).stem
    return f"S{idx} {stem}"[:48]
