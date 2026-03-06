"""
Settings page - view config and storage roots.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.app.controllers.settings_controller import SettingsController


def render_settings_page() -> None:
    """Render the settings page."""
    st.markdown(
        '<div class="main-header">⚙️ Settings</div>',
        unsafe_allow_html=True,
    )

    try:
        ctrl = SettingsController()
        roots = ctrl.get_storage_roots()

        st.subheader("Storage Roots")
        for name, path in roots.items():
            st.text(f"{name}: {path}")

        st.caption(
            "For full config editing, use the Configuration page (when a run is selected) or the CLI: transcriptx settings"
        )
    except Exception as e:
        st.error(f"Could not load settings: {e}")
