"""Build BlockContext from run-scoped session data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.web.blocks.context import BlockContext, build_block_context
from transcriptx.web.layouts.store import LayoutProfileStore
from transcriptx.web.services import ArtifactService, RunIndex, SubjectService

ACTIVE_LAYOUT_KEY = "active_layout_profile_id"
DEFAULT_LAYOUT_ID = "default"


def active_layout_id(session_state: dict[str, Any] | None = None) -> str:
    state = session_state if session_state is not None else st.session_state
    return str(state.get(ACTIVE_LAYOUT_KEY) or DEFAULT_LAYOUT_ID)


def set_active_layout_id(
    layout_id: str, session_state: dict[str, Any] | None = None
) -> None:
    state = session_state if session_state is not None else st.session_state
    state[ACTIVE_LAYOUT_KEY] = layout_id


def _layout_file_signature(layout_id: str) -> tuple[str, float] | None:
    """Return (path, mtime) of the yaml backing a layout id, or None if missing."""
    from transcriptx.web.layouts.store import PRESETS_DIR

    root = LayoutProfileStore.layouts_dir(None)
    for path in (root / f"{layout_id}.yaml", PRESETS_DIR / f"{layout_id}.yaml"):
        try:
            return str(path), path.stat().st_mtime
        except OSError:
            continue
    return None


@st.cache_data(show_spinner=False)
def _cached_layout(layout_id: str, path: str, mtime: float):
    return LayoutProfileStore.load_layout(layout_id)


def load_active_layout(session_state: dict[str, Any] | None = None):
    layout_id = active_layout_id(session_state)
    signature = _layout_file_signature(layout_id)
    if signature is None:
        layout_id = DEFAULT_LAYOUT_ID
        signature = _layout_file_signature(layout_id)
    if signature is None:
        # Preserve original behavior: missing default layout raises FileNotFoundError.
        return LayoutProfileStore.load_layout(DEFAULT_LAYOUT_ID)
    return _cached_layout(layout_id, *signature)


@st.cache_data(show_spinner=False)
def _cached_run_results(path_str: str, mtime: float) -> dict | None:
    try:
        return load_run_results(Path(path_str))
    except Exception:
        return None


def load_run_results_dict(run_root: Path) -> dict | None:
    """Load run_results.json if present (cached by file mtime)."""
    path = run_root / "run_results.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return _cached_run_results(str(path), mtime)


def _load_run_results(run_root: Path) -> dict | None:
    return load_run_results_dict(run_root)


def build_context_from_session(
    session_state: dict[str, Any],
    *,
    layout_profile_id: str | None = None,
) -> BlockContext | None:
    subject = SubjectService.resolve_current_subject(session_state)
    run_id = session_state.get("run_id")
    if not subject or not run_id:
        return None
    run_root = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )
    artifacts = ArtifactService.list_artifacts(run_root)
    health = ArtifactService.check_run_health(run_root)
    session_name = None
    if subject.subject_type == "transcript":
        session_name = f"{subject.subject_id}/{run_id}"
    return build_block_context(
        run_root=run_root,
        subject_type=subject.subject_type,
        subject_id=subject.subject_id,
        run_id=run_id,
        session_name=session_name,
        artifacts=artifacts,
        run_results=load_run_results_dict(run_root),
        layout_profile_id=layout_profile_id or active_layout_id(session_state),
        health=health,
    )


def empty_context(layout_profile_id: str | None = None) -> BlockContext:
    return build_block_context(
        run_root=None,
        subject_type=None,
        subject_id=None,
        run_id=None,
        session_name=None,
        artifacts=[],
        run_results=None,
        layout_profile_id=layout_profile_id or DEFAULT_LAYOUT_ID,
        health=None,
    )
