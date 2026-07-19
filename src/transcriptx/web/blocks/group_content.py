"""Helpers for dual group/member content loading in Insights and Overview blocks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import streamlit as st

from transcriptx.core.analysis.group_llm_synthesis.resolve import (
    is_group_run as _synth_is_group_run,
)
from transcriptx.core.pipeline.manifest_loader import load_group_member_runs
from transcriptx.web.blocks.loader import ArtifactContentLoader


@dataclass(frozen=True)
class GroupMemberRef:
    order_index: int
    transcript_path: str
    transcript_key: str
    run_id: str
    output_dir: str

    @property
    def label(self) -> str:
        stem = Path(self.transcript_path).stem if self.transcript_path else "session"
        return f"{self.order_index + 1}. {stem}"

    @property
    def storage_root(self) -> str:
        return str(Path(self.output_dir).resolve())


def is_group_run(run_root: Path | None) -> bool:
    if run_root is None:
        return False
    return _synth_is_group_run(Path(run_root))


def list_group_members(run_root: Path) -> list[GroupMemberRef]:
    raw = load_group_member_runs(Path(run_root) / "group_member_runs.json")
    members: list[GroupMemberRef] = []
    for row in raw:
        output_dir = str(row.get("output_dir") or "").strip()
        if not output_dir:
            continue
        try:
            order = int(row.get("order_index") or 0)
        except (TypeError, ValueError):
            order = 0
        members.append(
            GroupMemberRef(
                order_index=order,
                transcript_path=str(row.get("transcript_path") or ""),
                transcript_key=str(row.get("transcript_key") or ""),
                run_id=str(row.get("run_id") or ""),
                output_dir=output_dir,
            )
        )
    members.sort(key=lambda m: m.order_index)
    return members


def load_json_file(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_group_content_rows(
    run_root: Path,
    agg_id: str,
    content_rows_name: str,
) -> list[dict[str, Any]]:
    payload = load_json_file(Path(run_root) / agg_id / f"{content_rows_name}.json")
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def load_group_session_rows(run_root: Path, agg_id: str) -> list[dict[str, Any]]:
    payload = load_json_file(Path(run_root) / agg_id / "session_rows.json")
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def load_group_speaker_rows(run_root: Path, agg_id: str) -> list[dict[str, Any]]:
    payload = load_json_file(Path(run_root) / agg_id / "speaker_rows.json")
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def load_group_row_bundle(
    run_root: Path,
    agg_id: str,
    content_rows_name: str,
) -> dict[str, list[dict[str, Any]]]:
    """Load session_rows + named content_rows for a group aggregate id."""
    return {
        "session_rows": load_group_session_rows(run_root, agg_id),
        "content_rows": load_group_content_rows(run_root, agg_id, content_rows_name),
        "speaker_rows": load_group_speaker_rows(run_root, agg_id),
    }


def load_group_blob(
    run_root: Path,
    module: str,
    blob_name: str,
) -> dict[str, Any] | None:
    payload = load_json_file(Path(run_root) / module / f"{blob_name}.json")
    return payload if isinstance(payload, dict) else None


def load_member_module_json(
    loader: ArtifactContentLoader | None,
    member: GroupMemberRef,
    module: str,
    suffix: str,
) -> dict[str, Any] | None:
    if loader is None:
        return _load_member_suffix_from_disk(member, module, suffix, kind="json")
    payload = loader.load_json(module, suffix, storage_root=member.storage_root)
    if payload is not None:
        return payload
    return _load_member_suffix_from_disk(member, module, suffix, kind="json")


def load_member_module_text(
    loader: ArtifactContentLoader | None,
    member: GroupMemberRef,
    module: str,
    suffix: str,
) -> str | None:
    if loader is not None:
        text = loader.load_text(module, suffix, storage_root=member.storage_root)
        if text is not None:
            return text
    return _load_member_suffix_from_disk(member, module, suffix, kind="text")


def _rank_member_candidate(path: Path, module_dir: Path) -> tuple[int, int, str]:
    """Prefer data/global paths, then shallower paths under the module dir."""
    try:
        rel = path.relative_to(module_dir).as_posix()
    except ValueError:
        rel = path.name
    global_rank = (
        0 if "/data/global/" in f"/{rel}" or rel.startswith("data/global/") else 1
    )
    depth = rel.count("/")
    return (global_rank, depth, rel)


def _load_member_suffix_from_disk(
    member: GroupMemberRef,
    module: str,
    suffix: str,
    *,
    kind: str,
) -> Any | None:
    root = Path(member.output_dir)
    if not root.is_dir():
        return None
    module_dir = root / module
    search_root = module_dir if module_dir.is_dir() else root
    matches = [p for p in search_root.rglob(f"*{suffix}") if p.is_file()]
    if not matches:
        return None
    matches.sort(key=lambda p: _rank_member_candidate(p, search_root))
    path = matches[0]
    if kind == "json":
        payload = load_json_file(path)
        return payload if isinstance(payload, dict) else None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def select_group_member(
    members: Sequence[GroupMemberRef],
    *,
    key: str,
    label: str = "Session",
) -> GroupMemberRef | None:
    if not members:
        return None
    if len(members) == 1:
        return members[0]
    options = list(range(len(members)))
    choice = st.selectbox(
        label,
        options=options,
        format_func=lambda i: members[i].label,
        key=key,
    )
    return members[int(choice)]


def member_empty_hint(module: str) -> str:
    return (
        f"No `{module}` artifacts found for this session. "
        f"Open Artifacts or re-run group analysis with `{module}` selected."
    )


def group_rollup_empty_hint(module: str, *, content_name: str | None = None) -> str:
    target = content_name or module
    return (
        f"No group `{target}` rollup found. "
        f"Member `{module}` outputs may still be available under Per session."
    )
