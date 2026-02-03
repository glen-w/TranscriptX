"""
Data artifacts page for TranscriptX Studio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.web.services import ArtifactService


def render_data() -> None:
    session = st.session_state.get("selected_session")
    run_id = st.session_state.get("selected_run_id")
    if not session or not run_id:
        st.info("Select a session and run to view data artifacts.")
        return

    artifacts = ArtifactService.list_artifacts(session, run_id)
    data_artifacts = [
        a for a in artifacts if a.kind in {"data_json", "data_csv", "data_txt"}
    ]
    if not data_artifacts:
        st.warning("No data artifacts found.")
        return

    options = {a.id: f"{a.module or 'other'} • {a.rel_path}" for a in data_artifacts}
    selected_id = st.selectbox("Select data artifact", list(options.keys()), format_func=options.get)
    selected = next(a for a in data_artifacts if a.id == selected_id)

    run_dir = ArtifactService._resolve_run_dir(session, run_id)
    path = ArtifactService._resolve_safe_path(run_dir, selected.rel_path)
    if path is None or not path.exists():
        st.error("Artifact file missing.")
        return

    st.caption(f"{selected.rel_path} ({selected.mime})")

    if selected.kind == "data_csv":
        df = pd.read_csv(path)
        st.dataframe(df, width='stretch')
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
