"""Reusable artifact export panel (moved from Overview block)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import streamlit as st

from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.module_ui_groups import order_module_ids
from transcriptx.web.services import ArtifactService
from transcriptx.web.services.export_service import ExportService

HARD_CAP_BYTES = 2 * 1024 * 1024 * 1024
WARN_BYTES = 500 * 1024 * 1024


def resolve_export_selection(
    artifacts: Sequence[Artifact],
    export_mode: str,
    *,
    module_choice: str | None = None,
    speaker_choice: str | None = None,
    custom_ids: Sequence[str] | None = None,
    preselected_ids: Sequence[str] | None = None,
) -> list[Artifact]:
    """Pure selection resolution for export modes (testable without Streamlit)."""
    selected = list(artifacts)
    if export_mode == "Module":
        selected = [a for a in artifacts if a.module == module_choice]
    elif export_mode == "Speaker":
        selected = [a for a in artifacts if a.speaker == speaker_choice]
    elif export_mode == "Charts Only":
        selected = [a for a in artifacts if a.kind.startswith("chart")]
    elif export_mode == "Static Charts Only":
        selected = [a for a in artifacts if a.kind == "chart_static"]
    elif export_mode == "Data Only":
        selected = [a for a in artifacts if a.kind.startswith("data")]
    elif export_mode == "Custom Selection":
        chosen = set(custom_ids or ())
        if preselected_ids and not chosen:
            chosen = set(preselected_ids)
        selected = [a for a in artifacts if a.id in chosen]
    elif export_mode == "Selected":
        chosen = set(preselected_ids or ())
        selected = [a for a in artifacts if a.id in chosen]
    return selected


@st.fragment
def render_export_panel_ui(
    run_root: Path,
    artifacts: Sequence[Artifact],
    *,
    key_prefix: str = "export",
    preselected_ids: Sequence[str] | None = None,
) -> None:
    """Render export controls and download flow."""
    st.subheader("Export")
    modes = [
        "All",
        "Module",
        "Speaker",
        "Charts Only",
        "Static Charts Only",
        "Data Only",
        "Custom Selection",
    ]
    if preselected_ids:
        modes = ["Selected", *modes]

    export_mode = st.radio(
        "Export Options",
        modes,
        key=f"{key_prefix}_mode",
    )
    module_choice = None
    speaker_choice = None
    custom_ids: list[str] = []

    if export_mode == "Module":
        module_options = order_module_ids({a.module for a in artifacts if a.module})
        module_choice = st.selectbox(
            "Module",
            module_options,
            format_func=format_module_option,
            key=f"{key_prefix}_module",
        )
    elif export_mode == "Speaker":
        speaker_options = sorted({a.speaker for a in artifacts if a.speaker})
        speaker_choice = st.selectbox(
            "Speaker",
            speaker_options,
            key=f"{key_prefix}_speaker",
        )
    elif export_mode == "Custom Selection":
        options = {a.id: a.rel_path for a in artifacts}
        default = [i for i in (preselected_ids or ()) if i in options]
        custom_ids = st.multiselect(
            "Artifacts",
            list(options.keys()),
            default=default,
            format_func=lambda key: options.get(key, key),
            key=f"{key_prefix}_artifacts",
        )

    selected = resolve_export_selection(
        artifacts,
        export_mode,
        module_choice=module_choice,
        speaker_choice=speaker_choice,
        custom_ids=custom_ids,
        preselected_ids=preselected_ids,
    )

    if not selected:
        st.info("No artifacts selected for export.")
        return

    total_bytes = sum(a.bytes for a in selected)
    st.caption(f"Selection size: {total_bytes / (1024 * 1024):.1f} MB")
    confirm_large = True
    if total_bytes > WARN_BYTES:
        st.warning("Large export (> 500MB). Confirm before exporting.")
        confirm_large = st.checkbox(
            "I understand this may take time.",
            key=f"{key_prefix}_confirm_large",
        )
    if total_bytes > HARD_CAP_BYTES:
        st.error("Export exceeds 2GB hard cap.")
        return
    if st.button(
        "Create Export", disabled=not confirm_large, key=f"{key_prefix}_create"
    ):
        export_path = ExportService.zip_artifacts(run_root, [a.id for a in selected])
        if export_path:
            try:
                payload = ArtifactService.read_for_download(export_path)
                st.download_button(
                    "Download Export",
                    data=payload,
                    file_name=export_path.name,
                    key=f"{key_prefix}_download",
                )
            except Exception as exc:
                st.error(f"Export failed: {exc}")
