"""
Batch Operations page.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.batch_controller import BatchController
from transcriptx.app.models.requests import BatchAnalysisRequest
from transcriptx.web.cache_helpers import (
    cached_list_transcripts,
    cached_get_module_info_list,
)


def render_batch_ops_page() -> None:
    """Render the batch operations page."""
    st.markdown(
        '<div class="main-header">📦 Batch Operations</div>',
        unsafe_allow_html=True,
    )

    batch_ctrl = BatchController()
    transcripts = cached_list_transcripts()

    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    # Build options: display label = base_name, value = path string
    transcript_options = {str(t.path): t.base_name for t in transcripts}
    option_keys = list(transcript_options.keys())

    selected_keys = st.multiselect(
        "Select transcripts to process",
        options=option_keys,
        default=[],
        format_func=lambda k: transcript_options.get(k, k),
        key="batch_transcripts",
        help="Choose one or more transcripts from your library",
    )
    selected_paths = [Path(p) for p in selected_keys] if selected_keys else []

    mode = st.selectbox("Analysis mode", ["quick", "full"], index=0, key="batch_mode")
    modules_info = cached_get_module_info_list()
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

    if st.button("Run Batch Analysis", type="primary", key="batch_run"):
        if not selected_paths:
            st.warning("Select at least one transcript to process.")
        else:
            request = BatchAnalysisRequest(
                transcript_paths=selected_paths,
                analysis_mode=mode,
                selected_modules=selected if selected else None,
                skip_speaker_gate=skip_speaker_gate,
                persist=persist,
            )
            with st.spinner("Running batch analysis..."):
                result = batch_ctrl.run_batch_analysis(request)
            if result.success:
                st.success(
                    result.message
                    or f"Processed {result.transcript_count} transcript(s)."
                )
            else:
                st.error("Batch analysis completed with errors.")
                for e in result.errors:
                    st.error(e)
