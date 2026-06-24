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


def load_active_layout(session_state: dict[str, Any] | None = None):
    layout_id = active_layout_id(session_state)
    try:
        return LayoutProfileStore.load_layout(layout_id)
    except FileNotFoundError:
        return LayoutProfileStore.load_layout(DEFAULT_LAYOUT_ID)


def load_run_results_dict(run_root: Path) -> dict | None:
    """Load run_results.json if present."""
    path = run_root / "run_results.json"
    if not path.exists():
        return None
    try:
        return load_run_results(path)
    except Exception:
        return None


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
