"""
Data artifacts page for TranscriptX Studio.

Filter and preview widgets run in ``@st.fragment`` so subview/artifact changes do
not trigger a full-app rerun.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.web.blocks.filters.subview_slice import (
    filter_artifacts_by_subview_slice,
    render_subview_slice_filter,
)
from transcriptx.web.blocks.implementations.data import render_artifact_file_preview
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_ui_groups import module_sort_key
from transcriptx.web.services import ArtifactService, RunIndex, SubjectService
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_ARTIFACT,
    DATA_KEY_ARTIFACT_PRESET,
)

_DATA_HELP_PREREQ = (
    "**Data** lists structured outputs (tables, JSON) produced by analysis modules."
)
_DATA_HELP_LOADED = "Choose a subview or slice if present, then pick a file to preview."


@st.fragment
def _data_browser_fragment(run_root: Path, data_artifacts: list[Artifact]) -> None:
    """Subview, slice, and artifact preview without full-app rerun."""
    slice_state = render_subview_slice_filter(
        data_artifacts,
        subview_key="data_subview_tabs",
        slice_key="data_slice_selector",
    )
    filtered = filter_artifacts_by_subview_slice(
        data_artifacts,
        subview=slice_state.subview,
        slice_id=slice_state.slice_id,
    )

    if not filtered:
        render_empty_state(
            "filtered_to_zero",
            "No data files match these filters",
            "Choose **All** subviews or another slice.",
            primary_action=("Overview", "Overview"),
            secondary_action=None,
        )
        return

    filtered = sorted(
        filtered,
        key=lambda a: (module_sort_key(a.module or None), a.rel_path or ""),
    )

    options = {a.id: f"{a.module or 'other'} • {a.rel_path}" for a in filtered}
    option_keys = list(options.keys())
    selected_id = st.selectbox(
        "Select data artifact",
        [""] + option_keys,
        format_func=lambda k: (
            SELECTBOX_PLACEHOLDER_ARTIFACT if k == "" else options.get(k, k)
        ),
        index=0,
        key="data_artifact_selector",
    )
    if not selected_id:
        render_empty_state(
            "missing_prerequisite",
            "Select a file",
            "Choose a data artifact from the list to preview its contents.",
            primary_action=("Charts", "Charts"),
            secondary_action=None,
        )
        return
    selected = next(a for a in filtered if a.id == selected_id)

    render_artifact_file_preview(run_root, selected)


def render_data() -> None:
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        render_page_shell(
            "Data",
            "Preview JSON, CSV, and text artifacts from the current run.",
            badges=None,
            actions=None,
        )
        render_empty_state(
            "missing_prerequisite",
            "Select a subject and run",
            "Pick a transcript or group and run in the sidebar to browse data files.",
            primary_action=("Open Library", "Library"),
            secondary_action=("Overview", "Overview"),
        )
        render_page_help(_DATA_HELP_PREREQ)
        return

    run_root = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )

    artifacts = ArtifactService.list_artifacts(run_root)
    data_artifacts = [
        a for a in artifacts if a.kind in {"data_json", "data_csv", "data_txt"}
    ]
    preset = st.session_state.pop(DATA_KEY_ARTIFACT_PRESET, None)
    if preset and any(a.id == preset for a in data_artifacts):
        st.session_state["data_artifact_selector"] = preset

    render_page_shell(
        "Data",
        "Preview JSON, CSV, and text artifacts from the current run.",
        badges=[
            f"{len(data_artifacts)} files" if data_artifacts else "Missing",
        ],
        actions=None,
    )

    if not data_artifacts:
        render_empty_state(
            "no_results_yet",
            "No data artifacts in this run",
            "Modules may not have emitted tabular/JSON outputs, or they were skipped.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Overview", "Overview"),
        )
        render_page_help(_DATA_HELP_LOADED)
        return

    _data_browser_fragment(run_root, data_artifacts)
    render_page_help(_DATA_HELP_LOADED)
