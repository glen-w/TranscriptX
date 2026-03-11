"""
Profiles page - view and manage analysis profiles.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.app.controllers.profile_controller import ProfileController
from transcriptx.web.cache_helpers import cached_get_available_modules


@st.cache_data(ttl=60, show_spinner=False)
def _cached_list_profiles(module: str) -> list:
    return ProfileController().list_profiles(module)


def render_profiles_page() -> None:
    """Render the profiles page."""
    st.markdown(
        '<div class="main-header">📋 Profiles</div>',
        unsafe_allow_html=True,
    )

    try:
        ctrl = ProfileController()
        modules = cached_get_available_modules()

        module_choice = st.selectbox(
            "Module",
            modules,
            format_func=lambda m: m.replace("_", " ").title(),
            key="profiles_module",
        )
        if module_choice:
            profiles = _cached_list_profiles(module_choice)
            active = ctrl.get_active_profile(module_choice)
            st.metric("Profiles", len(profiles))
            st.caption(f"Active: {active}")
            for p in profiles:
                with st.expander(p):
                    data = ctrl.load_profile(module_choice, p)
                    st.json(data)
    except Exception as e:
        st.error(f"Could not load profiles: {e}")
