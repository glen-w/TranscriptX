"""
Data artifacts page for TranscriptX Studio.

Filter and preview widgets run in ``@st.fragment`` so subview/artifact changes do
not trigger a full-app rerun.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_ui_groups import module_sort_key
from transcriptx.web.services import ArtifactService, RunIndex, SubjectService
from transcriptx.web.state import SELECTBOX_PLACEHOLDER_ARTIFACT

_DATA_HELP_PREREQ = (
    "**Data** lists structured outputs (tables, JSON) produced by analysis modules."
)
_DATA_HELP_LOADED = "Choose a subview or slice if present, then pick a file to preview."


@st.fragment
def _data_browser_fragment(run_root: Path, data_artifacts: list[Artifact]) -> None:
    """Subview, slice, and artifact preview without full-app rerun."""
    subviews = sorted({a.subview for a in data_artifacts if a.subview})
    subview_filter = None
    slice_filter = None
    if subviews:
        tab = st.radio(
            "Subview",
            ["All"] + subviews,
            index=0,
            horizontal=True,
            key="data_subview_tabs",
        )
        subview_filter = None if tab == "All" else tab
        if subview_filter in {"by_session", "by_speaker"}:
            slice_ids = sorted(
                {
                    a.slice_id
                    for a in data_artifacts
                    if a.subview == subview_filter and a.slice_id
                }
            )
            if slice_ids:
                slice_choice = st.selectbox(
                    "Slice",
                    ["All"] + slice_ids,
                    index=0,
                    key="data_slice_selector",
                )
                slice_filter = None if slice_choice == "All" else slice_choice

    filtered = data_artifacts
    if subview_filter:
        filtered = [
            a
            for a in data_artifacts
            if a.subview == subview_filter
            and (slice_filter is None or a.slice_id == slice_filter)
        ]

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

    path = ArtifactService._resolve_safe_path(run_root, selected.rel_path)
    if path is None or not path.exists():
        render_empty_state(
            "error_degraded",
            "Artifact missing on disk",
            "The manifest references this path but the file is not available.",
            primary_action=("Diagnostics", "Diagnostics"),
            secondary_action=("Overview", "Overview"),
        )
        return

    st.caption(f"{selected.rel_path} ({selected.mime})")

    if selected.kind == "data_csv":
        df = pd.read_csv(path)
        st.dataframe(df, width="stretch")
    elif selected.kind == "data_json":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        st.json(data)
    elif selected.kind == "data_txt":
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() == ".md":
            st.markdown(content)
        else:
            st.text_area("Text", content, height=400)
    else:
        st.write(Path(path).read_text())


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
