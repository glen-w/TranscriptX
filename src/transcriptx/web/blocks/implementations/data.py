"""Data page block implementations."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services import ArtifactService


def render_artifact_file_preview(run_root: Path, selected: Artifact) -> None:
    """Preview a single data artifact on disk."""
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


def render_data_artifact_preview(ctx: BlockContext, _placement: BlockPlacement) -> None:
    if ctx.run_root is None:
        st.info("Select a run to preview data artifacts.")
        return
    selected_id = st.session_state.get("data_artifact_selector")
    if not selected_id:
        st.caption("Select a data artifact in the browser above.")
        return
    selected = next((a for a in ctx.artifacts if a.id == selected_id), None)
    if selected is None:
        st.caption("Selected artifact is not in the current run manifest.")
        return
    render_artifact_file_preview(ctx.run_root, selected)
