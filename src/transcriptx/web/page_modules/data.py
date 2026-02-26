"""
Data artifacts page for TranscriptX Studio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.web.services import ArtifactService, RunIndex, SubjectService


def render_data() -> None:
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        st.info("Select a subject and run to view data artifacts.")
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
    if not data_artifacts:
        st.warning("No data artifacts found.")
        return

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

    if subview_filter:
        data_artifacts = [
            a
            for a in data_artifacts
            if a.subview == subview_filter
            and (slice_filter is None or a.slice_id == slice_filter)
        ]

    if not data_artifacts:
        st.info("No data artifacts match the current filters.")
        return

    options = {a.id: f"{a.module or 'other'} • {a.rel_path}" for a in data_artifacts}
    selected_id = st.selectbox(
        "Select data artifact", list(options.keys()), format_func=options.get
    )
    selected = next(a for a in data_artifacts if a.id == selected_id)

    path = ArtifactService._resolve_safe_path(run_root, selected.rel_path)
    if path is None or not path.exists():
        st.error("Artifact file missing.")
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
