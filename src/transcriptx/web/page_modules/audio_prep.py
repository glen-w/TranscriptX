"""
Audio Prep page - convert, merge, compress, preprocess.
"""

from __future__ import annotations

import streamlit as st


def render_audio_prep_page() -> None:
    """Render the audio prep page."""
    st.markdown(
        '<div class="main-header">📁 Audio Prep</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Audio prep (convert, merge, compress, preprocess) is available via CLI: "
        "`transcriptx prep-audio` and `transcriptx process-wav`. "
        "GUI support coming in a future release."
    )
