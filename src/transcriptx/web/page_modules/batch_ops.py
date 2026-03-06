"""
Batch Operations page.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.batch_controller import BatchController
from transcriptx.app.controllers.library_controller import LibraryController
from transcriptx.app.module_resolution import get_module_info_list
from transcriptx.app.models.requests import BatchAnalysisRequest


def render_batch_ops_page() -> None:
    """Render the batch operations page."""
    st.markdown(
        '<div class="main-header">📦 Batch Operations</div>',
        unsafe_allow_html=True,
    )

    lib_ctrl = LibraryController()
    batch_ctrl = BatchController()
    transcripts = lib_ctrl.list_transcripts()

    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    folder_input = st.text_input(
        "Folder path",
        value=str(Path(transcripts[0].path).parent) if transcripts else "",
        key="batch_folder",
        help="Path to folder containing transcript JSON files",
    )
    folder = Path(folder_input) if folder_input else None

    mode = st.selectbox("Analysis mode", ["quick", "full"], index=0, key="batch_mode")
    modules_info = get_module_info_list()
    module_ids = [m.id for m in modules_info]
    selected = st.multiselect(
        "Modules (empty = defaults)",
        options=module_ids,
        default=[],
        key="batch_modules",
    )
    skip_speaker_gate = st.checkbox(
        "Skip speaker gate", value=False, key="batch_skip_gate"
    )
    persist = st.checkbox("Persist to DB", value=False, key="batch_persist")

    if st.button("Run Batch Analysis", type="primary", key="batch_run") and folder:
        request = BatchAnalysisRequest(
            folder=folder,
            analysis_mode=mode,
            selected_modules=selected if selected else None,
            skip_speaker_gate=skip_speaker_gate,
            persist=persist,
        )
        with st.spinner("Running batch analysis..."):
            result = batch_ctrl.run_batch_analysis(request)
        if result.success:
            st.success(
                result.message or f"Processed {result.transcript_count} transcript(s)."
            )
        else:
            st.error("Batch analysis completed with errors.")
            for e in result.errors:
                st.error(e)
