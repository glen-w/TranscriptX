"""
Run Analysis page - configure and execute single-transcript analysis.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.analysis_controller import AnalysisController
from transcriptx.app.controllers.library_controller import LibraryController
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.output_capture import capture_output
from transcriptx.web.state import SELECTED_TRANSCRIPT_PATH
from transcriptx.web.components.progress_panel import StreamlitProgressCallback


def render_run_analysis_page() -> None:
    """Render the Run Analysis page with form and execution."""
    st.markdown(
        '<div class="main-header">📊 Run Analysis</div>',
        unsafe_allow_html=True,
    )

    lib_ctrl = LibraryController()
    analysis_ctrl = AnalysisController()

    transcripts = lib_ctrl.list_transcripts()
    transcript_options = [str(t.path) for t in transcripts]
    transcript_labels = [t.base_name for t in transcripts]

    selected_path = st.session_state.get(SELECTED_TRANSCRIPT_PATH)
    default_idx = 0
    if selected_path and selected_path in transcript_options:
        default_idx = transcript_options.index(selected_path)

    transcript_choice = st.selectbox(
        "Transcript",
        range(len(transcript_options)),
        format_func=lambda i: (
            transcript_labels[i] if i < len(transcript_labels) else ""
        ),
        index=default_idx if default_idx < len(transcript_options) else 0,
        key="run_analysis_transcript",
    )
    transcript_path = (
        Path(transcript_options[transcript_choice]) if transcript_options else None
    )

    mode = st.radio(
        "Analysis mode", ["quick", "full"], horizontal=True, key="run_analysis_mode"
    )
    profile = None
    if mode == "full":
        profile = st.selectbox(
            "Profile",
            ["balanced", "academic", "business", "casual", "technical", "interview"],
            key="run_analysis_profile",
        )

    available = analysis_ctrl.get_available_modules()
    default_modules = (
        analysis_ctrl.get_default_modules([str(transcript_path)])
        if transcript_path
        else []
    )
    use_defaults = st.checkbox(
        "Use recommended modules", value=True, key="run_analysis_use_defaults"
    )
    if use_defaults:
        selected_modules = default_modules
        st.caption(
            f"Modules: {', '.join(selected_modules[:8])}{'...' if len(selected_modules) > 8 else ''}"
        )
    else:
        selected_modules = st.multiselect(
            "Select modules",
            available,
            default=default_modules[:5] if default_modules else [],
            key="run_analysis_modules",
        )

    if st.session_state.get("analysis_run_in_progress", False):
        st.warning("Analysis is running...")
        return

    if st.button("▶ Run Analysis", type="primary", key="run_analysis_launch"):
        if not transcript_path or not transcript_path.exists():
            st.error("Please select a valid transcript.")
            return
        if not selected_modules:
            st.error("Please select at least one module.")
            return

        request = AnalysisRequest(
            transcript_path=transcript_path,
            mode=mode,
            modules=selected_modules,
            profile=profile,
            skip_speaker_mapping=True,
        )

        errors = analysis_ctrl.validate_readiness(request)
        if errors:
            for e in errors:
                st.error(e)
            return

        st.session_state["analysis_run_in_progress"] = True
        progress = StreamlitProgressCallback()

        with st.status("Running analysis...", expanded=True) as status:
            try:
                with capture_output() as (stdout_buf, stderr_buf):
                    result = analysis_ctrl.run_analysis(request, progress=progress)
            finally:
                st.session_state["analysis_run_in_progress"] = False

            captured = stdout_buf.getvalue() + stderr_buf.getvalue()

            if result.success:
                status.update(label="✓ Analysis complete", state="complete")
                st.success(f"Analysis completed. Output: {result.run_dir}")
                if result.modules_executed:
                    st.caption(f"Modules run: {', '.join(result.modules_executed)}")
                if result.errors:
                    st.warning(f"Warnings: {len(result.errors)}")
                    for e in result.errors[:5]:
                        st.caption(f"  • {e}")
                if captured:
                    with st.expander("Log output"):
                        st.text(captured)
            else:
                status.update(label="✗ Analysis failed", state="error")
                st.error("Analysis failed")
                for e in result.errors:
                    st.error(e)
                if captured:
                    with st.expander("Log output"):
                        st.text(captured)
