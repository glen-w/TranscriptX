"""
Presentation-oriented artifact index over ArtifactService.

Two independent ordering dimensions:
- module taxonomy (presentation_group / module_rank) for Charts and module pickers
- artifact role (role_rank) for Browse / Export selectors

Cache contract: immutable index keyed by subject/run plus manifest and
run_results.json signatures. Do not stash indefinitely in session state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Literal, Sequence

import streamlit as st

from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_ui_groups import (
    TECHNICAL_OTHER_KEY,
    TECHNICAL_OTHER_TITLE,
    group_title_for_module_id,
    module_sort_key,
    order_module_ids,
    presentation_group_for_module,
)
from transcriptx.web.services.artifact_service import ArtifactService

ArtifactRole = Literal[
    "summary",
    "report",
    "chart",
    "structured_data",
    "diagnostics",
    "raw_technical",
]
SourceKind = Literal["transcript", "group_aggregate", "member_session"]

_ROLE_RANK: dict[str, int] = {
    "summary": 0,
    "report": 1,
    "chart": 2,
    "structured_data": 3,
    "diagnostics": 4,
    "raw_technical": 5,
}

_SUMMARY_MODULES = frozenset(
    {
        "llm_summary",
        "narrative_summary",
        "llm_speaker_summary",
        "llm_action_items",
        "summary",
        "highlights",
        "insights",
    }
)
_SUMMARY_STEM_HINTS = (
    "_llm_summary",
    "_narrative_summary",
    "_llm_speaker_summary",
    "_llm_action_items",
    "_summary",
    "_highlights",
)
_DIAGNOSTIC_NAMES = frozenset(
    {
        "run_results.json",
        "manifest.json",
        "group_member_runs.json",
        "group_run_metadata.json",
    }
)
_REPORT_NAMES = frozenset({"report.json", "report.md", "report.txt"})


class ArtifactSourceFilter(str, Enum):
    ALL = "all"
    GROUP_AGGREGATE = "group_aggregate"
    MEMBER_SESSIONS = "member_sessions"


@dataclass(frozen=True)
class ArtifactIndexEntry:
    artifact: Artifact
    presentation_group: str
    presentation_group_title: str
    module_rank: tuple
    artifact_role: ArtifactRole
    role_rank: int
    source_kind: SourceKind
    member_session: str | None
    preview_eligible: bool
    is_chart: bool
    is_exportable: bool
    size_label: str

    @property
    def id(self) -> str:
        return self.artifact.id

    @property
    def module(self) -> str | None:
        return self.artifact.module


@dataclass(frozen=True)
class ArtifactIndex:
    entries: tuple[ArtifactIndexEntry, ...]
    subject_scope: str
    subject_id: str
    run_id: str
    manifest_sig: str
    run_results_sig: str

    def by_id(self) -> dict[str, ArtifactIndexEntry]:
        return {e.id: e for e in self.entries}

    def artifacts(self) -> list[Artifact]:
        return [e.artifact for e in self.entries]

    def chart_entries(self) -> list[ArtifactIndexEntry]:
        return [e for e in self.entries if e.is_chart]

    def count_by_role(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.artifact_role] = counts.get(e.artifact_role, 0) + 1
        return counts


def file_signature(path: Path) -> str:
    """Stable signature from existence + mtime_ns + size (not full content hash)."""
    try:
        if not path.exists():
            return "missing"
        st_ = path.stat()
        return f"{st_.st_mtime_ns}:{st_.st_size}"
    except OSError:
        return "error"


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def classify_artifact_role(artifact: Artifact) -> ArtifactRole:
    name = Path(artifact.rel_path).name.lower()
    kind = (artifact.kind or "").lower()
    module = artifact.module or ""
    rel_lower = artifact.rel_path.lower()

    if name in _DIAGNOSTIC_NAMES or ".transcriptx/" in rel_lower:
        return "diagnostics"
    if name in _REPORT_NAMES:
        return "report"
    if kind.startswith("chart"):
        return "chart"
    if module in _SUMMARY_MODULES or any(h in name for h in _SUMMARY_STEM_HINTS):
        return "summary"
    if kind.startswith("data") or kind in {"data_json", "data_csv", "data_txt"}:
        return "structured_data"
    if kind in {"other", "binary", "audio", "unknown"}:
        return "raw_technical"
    return "structured_data"


def classify_source_kind(artifact: Artifact) -> SourceKind:
    if "member_session" in artifact.tags or artifact.storage_root:
        return "member_session"
    # Group-run aggregate artifacts live on the group run root (no storage_root).
    # Callers may still be transcript-scoped; default is transcript unless tagged.
    if any(t.startswith("group") for t in artifact.tags):
        return "group_aggregate"
    return "transcript"


def _member_session_label(artifact: Artifact) -> str | None:
    if "member_session" not in artifact.tags and not artifact.storage_root:
        return None
    title = artifact.title or ""
    if ":" in title:
        return title.split(":", 1)[0].strip() or None
    if artifact.slice_id:
        return artifact.slice_id
    if artifact.storage_root:
        return Path(artifact.storage_root).name
    return None


def _preview_eligible(artifact: Artifact) -> bool:
    kind = (artifact.kind or "").lower()
    if kind.startswith("chart"):
        return True
    if kind.startswith("data"):
        return True
    mime = (artifact.mime or "").lower()
    return mime.startswith("text/") or mime in {
        "application/json",
        "application/javascript",
        "image/png",
        "image/jpeg",
        "image/svg+xml",
        "image/webp",
    }


def build_entry(artifact: Artifact, *, is_group_run: bool) -> ArtifactIndexEntry:
    group_key, group_title = presentation_group_for_module(artifact.module)
    if group_key == TECHNICAL_OTHER_KEY:
        group_title = TECHNICAL_OTHER_TITLE
    elif not group_title:
        group_title = (
            group_title_for_module_id(artifact.module or "") or TECHNICAL_OTHER_TITLE
        )

    role = classify_artifact_role(artifact)
    source = classify_source_kind(artifact)
    if is_group_run and source == "transcript" and not artifact.storage_root:
        source = "group_aggregate"

    return ArtifactIndexEntry(
        artifact=artifact,
        presentation_group=group_key,
        presentation_group_title=group_title,
        module_rank=module_sort_key(artifact.module),
        artifact_role=role,
        role_rank=_ROLE_RANK[role],
        source_kind=source,
        member_session=_member_session_label(artifact),
        preview_eligible=_preview_eligible(artifact),
        is_chart=(artifact.kind or "").startswith("chart"),
        is_exportable=True,
        size_label=_format_size(int(artifact.bytes or 0)),
    )


def browse_sort_key(entry: ArtifactIndexEntry) -> tuple:
    return (
        entry.role_rank,
        entry.module_rank,
        entry.source_kind,
        entry.artifact.rel_path,
        entry.id,
    )


def charts_module_sort_key(entry: ArtifactIndexEntry) -> tuple:
    return (
        entry.module_rank,
        entry.artifact.title or "",
        entry.artifact.rel_path,
        entry.id,
    )


def order_artifacts_for_browse(
    entries: Sequence[ArtifactIndexEntry],
) -> list[ArtifactIndexEntry]:
    return sorted(entries, key=browse_sort_key)


def order_entries_for_charts(
    entries: Sequence[ArtifactIndexEntry],
) -> list[ArtifactIndexEntry]:
    return sorted(entries, key=charts_module_sort_key)


def filter_by_source(
    entries: Sequence[ArtifactIndexEntry],
    source_filter: ArtifactSourceFilter | str,
) -> list[ArtifactIndexEntry]:
    filt = (
        source_filter
        if isinstance(source_filter, ArtifactSourceFilter)
        else ArtifactSourceFilter(source_filter)
    )
    if filt == ArtifactSourceFilter.ALL:
        return list(entries)
    if filt == ArtifactSourceFilter.MEMBER_SESSIONS:
        return [e for e in entries if e.source_kind == "member_session"]
    return [e for e in entries if e.source_kind != "member_session"]


def order_modules_for_charts(entries: Iterable[ArtifactIndexEntry]) -> list[str]:
    modules = {e.module or "Other" for e in entries}
    return order_module_ids(modules)


def _is_group_run(run_root: Path) -> bool:
    return (run_root / "group_member_runs.json").exists()


def _build_index_uncached(
    run_root: Path,
    *,
    subject_scope: str,
    subject_id: str,
    run_id: str,
    manifest_sig: str,
    run_results_sig: str,
) -> ArtifactIndex:
    artifacts = ArtifactService.list_artifacts(run_root)
    is_group = _is_group_run(run_root)
    entries = tuple(build_entry(a, is_group_run=is_group) for a in artifacts)
    return ArtifactIndex(
        entries=entries,
        subject_scope=subject_scope,
        subject_id=subject_id,
        run_id=run_id,
        manifest_sig=manifest_sig,
        run_results_sig=run_results_sig,
    )


@st.cache_data(show_spinner=False)
def _cached_artifact_index(
    run_root_str: str,
    subject_scope: str,
    subject_id: str,
    run_id: str,
    manifest_sig: str,
    run_results_sig: str,
) -> ArtifactIndex:
    return _build_index_uncached(
        Path(run_root_str),
        subject_scope=subject_scope,
        subject_id=subject_id,
        run_id=run_id,
        manifest_sig=manifest_sig,
        run_results_sig=run_results_sig,
    )


def build_artifact_index(
    run_root: Path,
    *,
    subject_scope: str = "",
    subject_id: str = "",
    run_id: str = "",
) -> ArtifactIndex:
    """Build or reuse a signature-keyed immutable artifact index."""
    root = Path(run_root)
    rid = run_id or root.name
    manifest_sig = file_signature(root / "manifest.json")
    run_results_sig = file_signature(root / "run_results.json")
    return _cached_artifact_index(
        str(root.resolve()),
        subject_scope,
        subject_id,
        rid,
        manifest_sig,
        run_results_sig,
    )


def build_artifact_index_uncached(
    run_root: Path,
    *,
    subject_scope: str = "",
    subject_id: str = "",
    run_id: str = "",
) -> ArtifactIndex:
    """Build index without Streamlit cache (tests / non-UI callers)."""
    root = Path(run_root)
    rid = run_id or root.name
    return _build_index_uncached(
        root,
        subject_scope=subject_scope,
        subject_id=subject_id,
        run_id=rid,
        manifest_sig=file_signature(root / "manifest.json"),
        run_results_sig=file_signature(root / "run_results.json"),
    )
