"""
Speaker Identification page.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.speaker_controller import SpeakerController
from transcriptx.app.controllers.library_controller import LibraryController
from transcriptx.app.models.requests import SpeakerIdentificationRequest
from transcriptx.web.state import SELECTED_TRANSCRIPT_PATH


def render_speaker_id_page() -> None:
    """Render the speaker identification page."""
    st.markdown(
        '<div class="main-header">🗣️ Speaker Identification</div>',
        unsafe_allow_html=True,
    )

    lib_ctrl = LibraryController()
    speaker_ctrl = SpeakerController()
    transcripts = lib_ctrl.list_transcripts()

    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    selected_path = st.session_state.get(SELECTED_TRANSCRIPT_PATH)
    options = [str(t.path) for t in transcripts]
    labels = [t.base_name for t in transcripts]
    default_idx = options.index(selected_path) if selected_path in options else 0

    idx = st.selectbox(
        "Transcript",
        range(len(options)),
        format_func=lambda i: labels[i],
        index=default_idx,
        key="speaker_id_transcript",
    )
    path = Path(options[idx])

    skip_rename = st.checkbox(
        "Skip transcript rename (avoids interactive prompt)",
        value=True,
        key="speaker_id_skip_rename",
    )
    if st.button("Identify Speakers", type="primary", key="speaker_id_run"):
        request = SpeakerIdentificationRequest(
            transcript_paths=[path],
            overwrite=False,
            skip_rename=skip_rename,
        )
        with st.spinner("Identifying speakers..."):
            result = speaker_ctrl.identify_speakers(request)
        if result.success:
            st.success(f"Identified {result.speakers_identified} speakers.")
        else:
            st.error("Speaker identification failed.")
            for e in result.errors:
                st.error(e)
