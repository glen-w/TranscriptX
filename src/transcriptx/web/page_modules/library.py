"""
Library page - browse transcripts and audio inputs.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from transcriptx.app.controllers.library_controller import LibraryController


def render_library() -> None:
    """Render the transcript library page."""
    st.markdown(
        '<div class="main-header">📁 Library</div>',
        unsafe_allow_html=True,
    )

    try:
        lib_ctrl = LibraryController()
        transcripts = lib_ctrl.list_transcripts()

        if not transcripts:
            st.info(
                "No transcripts found. Add transcript JSON files to your configured transcript folder."
            )
            return

        df = pd.DataFrame(
            [
                {
                    "Name": m.base_name,
                    "Path": str(m.path),
                    "Speakers": (
                        "-" if m.speaker_count is None else str(m.speaker_count)
                    ),
                    "Duration": (
                        f"{m.duration_seconds:.1f}s" if m.duration_seconds else "-"
                    ),
                    "Has Analysis": "✓" if m.has_analysis_outputs else "—",
                    "Speakers Mapped": "✓" if m.has_speaker_map else "—",
                }
                for m in transcripts
            ]
        )

        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
        )

        st.divider()
        st.subheader("Actions")
        selected_idx = st.selectbox(
            "Select transcript",
            range(len(transcripts)),
            format_func=lambda i: transcripts[i].base_name,
            key="library_transcript_select",
        )
        if selected_idx is not None:
            selected = transcripts[selected_idx]
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Run Speaker ID", key="lib_speaker_id"):
                    st.session_state["selected_transcript_path"] = str(selected.path)
                    st.session_state["page"] = "Speaker Studio"
                    st.rerun()
            with col2:
                if st.button("Run Analysis", key="lib_run_analysis"):
                    st.session_state["selected_transcript_path"] = str(selected.path)
                    st.session_state["page"] = "Run Analysis"
                    st.rerun()

    except Exception as e:
        st.error(f"Could not load library: {e}")
