"""
Batch Operations page.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.batch_controller import BatchController
from transcriptx.app.models.requests import BatchAnalysisRequest
from transcriptx.web.cache_helpers import (
    get_cached_list_transcripts,
    cached_get_module_info_list,
    cached_get_transcript_summaries_for_paths,
)


def render_batch_ops_page() -> None:
    """Render the batch operations page."""
    st.markdown(
        '<div class="main-header">📦 Batch Operations</div>',
        unsafe_allow_html=True,
    )

    batch_ctrl = BatchController()
    transcripts = get_cached_list_transcripts()

    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    # Build options: display label = base_name (speaker status, segment count), value = path string
    transcript_options = {str(t.path): t.base_name for t in transcripts}
    option_keys = list(transcript_options.keys())
    paths_key = tuple(option_keys)
    summaries = cached_get_transcript_summaries_for_paths(paths_key)
    summary_by_path = {str(Path(s.path).resolve()): s for s in summaries}

    def _format_option(path_key: str) -> str:
        resolved = str(Path(path_key).resolve())
        s = summary_by_path.get(resolved)
        if s is not None:
            return f"{s.base_name} ({s.speaker_map_status}, {s.segment_count} segs)"
        return transcript_options.get(path_key, path_key)

    selected_keys = st.multiselect(
        "Select transcripts to process",
        options=option_keys,
        default=[],
        format_func=_format_option,
        key="batch_transcripts",
        help="Choose one or more transcripts. Labels show speaker identification status and segment count.",
    )
    selected_paths = [Path(p) for p in selected_keys] if selected_keys else []

    mode = st.selectbox("Analysis mode", ["quick", "full"], index=0, key="batch_mode")
    modules_info = cached_get_module_info_list()
    module_names = [m["name"] for m in modules_info]
    selected = st.multiselect(
        "Modules (empty = defaults)",
        options=module_names,
        default=[],
        key="batch_modules",
    )

    if st.button("Run Batch Analysis", type="primary", key="batch_run"):
        if not selected_paths:
            st.warning("Select at least one transcript to process.")
        else:
            request = BatchAnalysisRequest(
                transcript_paths=selected_paths,
                analysis_mode=mode,
                selected_modules=selected if selected else None,
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
