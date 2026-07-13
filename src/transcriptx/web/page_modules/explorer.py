"""Legacy File List (Explorer) page — redirects to Artifacts Browse."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.page_modules.artifacts import render_artifacts
from transcriptx.web.state import ARTIFACTS_KEY_SECTION, PAGE_KEY


def render_explorer() -> None:
    """Thin alias for bookmarked / stale Explorer sessions."""
    st.session_state[PAGE_KEY] = "Artifacts"
    st.session_state[ARTIFACTS_KEY_SECTION] = "Browse"
    render_artifacts()
