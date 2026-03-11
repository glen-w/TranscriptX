"""
Run Analysis page - configure and execute single-transcript analysis.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.analysis_controller import AnalysisController
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.output_capture import capture_output
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.web.state import SELECTED_TRANSCRIPT_PATH
from transcriptx.web.components.progress_panel import (
    SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.cache_helpers import (
    cached_list_transcripts,
    cached_get_available_modules,
    cached_get_default_modules,
)


def render_run_analysis_page() -> None:
    """Render the Run Analysis page with form and execution."""
    st.markdown(
        '<div class="main-header">📊 Run Analysis</div>',
        unsafe_allow_html=True,
    )

    analysis_ctrl = AnalysisController()

    transcripts = cached_list_transcripts()
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

    available = cached_get_available_modules()
    default_modules = (
        cached_get_default_modules(str(transcript_path)) if transcript_path else []
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

    # ------------------------------------------------------------------
    # If a run is in progress, show the live progress panel instead of
    # the launch button.  The snapshot is persisted in session_state so
    # Streamlit reruns rehydrate it without regressing to a generic message.
    # ------------------------------------------------------------------
    if st.session_state.get("analysis_run_in_progress", False):
        snapshot = st.session_state.get(SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(snapshot)
        else:
            st.info("Analysis is running…")
        return

    # Show panel for the last run (completed or failed) so the result persists
    # on the page after execution finishes without requiring a manual refresh.
    last_snapshot = st.session_state.get(SNAPSHOT_KEY)
    if last_snapshot and last_snapshot.get("status") in ("completed", "failed"):
        with st.expander("Last run progress", expanded=False):
            render_progress_panel(last_snapshot)

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

        # Seed a fresh snapshot in session state *before* setting the in-progress
        # flag so the progress panel has something to show on the very first rerun.
        st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(len(selected_modules))
        st.session_state["analysis_run_in_progress"] = True

        progress = StreamlitProgressCallback()
        snapshot = st.session_state[SNAPSHOT_KEY]

        with st.spinner("Running analysis…"):
            try:
                with capture_output() as (stdout_buf, stderr_buf):
                    result = analysis_ctrl.run_analysis(
                        request, progress=progress, snapshot=snapshot
                    )
            finally:
                st.session_state["analysis_run_in_progress"] = False

            captured = stdout_buf.getvalue() + stderr_buf.getvalue()

        # Render outcome after spinner finishes
        if result.success:
            st.success(
                f"Analysis completed successfully.  \nOutput: `{result.run_dir}`"
            )
            if result.modules_executed:
                st.caption(f"Modules run: {', '.join(result.modules_executed)}")
            if result.errors:
                st.warning(f"{len(result.errors)} warning(s) during run:")
                for e in result.errors[:5]:
                    st.caption(f"  • {e}")
        else:
            st.error("Analysis failed.")
            for e in result.errors:
                st.error(e)

        if captured:
            with st.expander("Full log output"):
                st.text(captured)
