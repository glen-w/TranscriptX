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

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".svg"}


def _is_image_artifact(selected: Artifact, path: Path) -> bool:
    kind = (selected.kind or "").lower()
    mime = (selected.mime or "").lower()
    if mime == "image/svg+xml" or path.suffix.lower() == ".svg":
        return False
    return (
        kind == "chart_static"
        or mime.startswith("image/")
        or path.suffix.lower() in _IMAGE_SUFFIXES
    )


def _is_html_artifact(selected: Artifact, path: Path) -> bool:
    kind = (selected.kind or "").lower()
    mime = (selected.mime or "").lower()
    return (
        kind == "chart_dynamic"
        or mime in {"text/html", "application/xhtml+xml"}
        or path.suffix.lower() in {".html", ".htm"}
    )


def render_artifact_file_preview(run_root: Path, selected: Artifact) -> None:
    """Preview a single data artifact on disk."""
    path = ArtifactService.resolve_artifact_source_path(run_root, selected)
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
    elif _is_image_artifact(selected, path):
        st.image(str(path), width="stretch")
    elif _is_html_artifact(selected, path):
        html = path.read_text(encoding="utf-8", errors="ignore")
        st.iframe(html, height=500)
    else:
        mime = (selected.mime or "").lower()
        if mime.startswith("text/") or path.suffix.lower() in _TEXT_SUFFIXES:
            try:
                st.write(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                st.info("Unable to decode this file as text. Use Download instead.")
        else:
            st.info("No inline preview for this binary artifact. Use Download instead.")


def render_data_artifact_preview(ctx: BlockContext, _placement: BlockPlacement) -> None:
    if ctx.run_root is None:
        st.info("Select a run to preview data artifacts.")
        return
    from transcriptx.web.state import ARTIFACTS_KEY_PREVIEW_ID

    selected_id = st.session_state.get(
        ARTIFACTS_KEY_PREVIEW_ID
    ) or st.session_state.get("data_artifact_selector")
    if not selected_id:
        st.caption("Select a data artifact in Artifacts → Preview.")
        return
    selected = next((a for a in ctx.artifacts if a.id == selected_id), None)
    if selected is None:
        st.caption("Selected artifact is not in the current run manifest.")
        return
    render_artifact_file_preview(ctx.run_root, selected)
