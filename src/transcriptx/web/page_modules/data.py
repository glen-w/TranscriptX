"""Legacy Data page — redirects to Artifacts Preview."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.page_modules.artifacts import render_artifacts
from transcriptx.web.state import ARTIFACTS_KEY_SECTION, PAGE_KEY


def render_data() -> None:
    """Thin alias for bookmarked / stale Data sessions."""
    st.session_state[PAGE_KEY] = "Artifacts"
    if not st.session_state.get(ARTIFACTS_KEY_SECTION):
        st.session_state[ARTIFACTS_KEY_SECTION] = "Preview"
    render_artifacts()
