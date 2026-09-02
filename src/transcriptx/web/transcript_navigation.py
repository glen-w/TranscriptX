"""Jump to a Transcript segment without importing the Transcript page module."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.models.search import NavRequest, SegmentRef
from transcriptx.web.state import (
    NAV_REQUEST_KEY,
    PAGE_KEY,
    apply_subject_context,
)


def navigate_to_segment(
    segment_ref: SegmentRef, highlight_query: str | None = None
) -> None:
    """Jump from search results into Transcript page context and rerun."""
    apply_subject_context(
        st.session_state,
        subject_type="transcript",
        subject_id=segment_ref.transcript_ref.session_slug,
        run_id=segment_ref.transcript_ref.run_id,
    )
    st.session_state[PAGE_KEY] = "Transcript"
    st.session_state[NAV_REQUEST_KEY] = NavRequest(
        segment_ref=segment_ref,
        highlight_query=highlight_query,
    )
    st.rerun()
